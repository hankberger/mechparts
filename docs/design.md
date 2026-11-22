# Design notes

This document records the main decisions behind the MVP, its known limitations and
suggested next steps.

## Architecture

```
HTTP (FastAPI)  ─┐
                 ├─>  PartService  ─>  registry ─> parts/*.py  (params, checks, build)
MCP (MCPServer) ─┘        │
                          ├─> Runner (worker processes, timeout) ─> build123d / OCCT
                          ├─> Storage (LocalStorage; S3-ready interface)
                          └─> Database (SQLite: catalog, geometries, files)
```

- **One service, two front ends.** `service.py` implements the five operations. The
  FastAPI app and the MCP server are thin adapters over it, so they cannot drift apart.
  The MCP server is mounted on the FastAPI app at `/mcp` (streamable HTTP), so one
  command starts both. `mechparts mcp` runs the same tools over stdio.
- **A part family is one module.** Each module declares a Pydantic parameter model, its
  metadata, `check()`, `computed()` and `build()`. The registry discovers modules that
  define `PART`. Pydantic gives the JSON Schema (with units, bounds, defaults and
  descriptions) and the first layer of validation for free. Unknown parameters are
  rejected, so agent typos surface instead of being silently ignored.
- **Errors are data.** Schema errors and cross-parameter errors share one shape
  (`param`, `code`, `message`, `allowed_min`, `allowed_max`). Messages say how to fix the
  problem with concrete numbers, so an agent can correct and retry without a human.

## Decisions

- **build123d** over CadQuery: a more Pythonic API, active development, and built-in
  STL, STEP and 3MF export. `bd_warehouse` (a build123d companion library) supplies the
  ISO thread used for male standoff studs.
- **MCP SDK v2** (`mcp>=2`, `MCPServer`). It was current when this was built; v1's
  `FastMCP` has been renamed.
- **Hash covers geometry, not format.** The spec keyed the cache on format as well, but
  `download(hash, format)` reads better if one hash names one geometry. The hash is
  sha256 over `(part_id, generator_version, normalized resolved params)`, truncated to
  128 bits. Floats are rounded to 6 decimals and defaults are filled in before hashing,
  so `{}` and the explicit defaults give the same hash. Asking for a different format of
  a known hash generates it on demand.
- **Byte-reproducible output.** STEP headers carry a timestamp and lib3mf stamps random
  UUIDs, so naive exports differ every run. STEP gets a fixed timestamp, and 3MF UUIDs
  are derived from the hash with zip entries dated 1980. `file_sha256` is therefore
  stable across machines with the same library versions.
- **Mesh quality is enforced on every generation.** The B-rep must be a single valid
  solid, and the STL is loaded with trimesh and must be watertight, consistently wound and
  a valid volume. Otherwise the request fails with `generation_failed`. STEP and 3MF
  requests run the same STL check.
- **Tessellation:** 0.01 mm chord error, 0.5 rad angular. Chord error is what matters for
  printing, and the looser angular limit keeps spline-heavy parts (gears) from producing
  millions of triangles.
- **Worker processes with a hard timeout.** OCCT is not thread-safe and can take a long
  time on unusual inputs. Generation runs in a `spawn` process pool (2 workers by
  default). A job that overruns `MECHPARTS_TIMEOUT` kills the pool, which is then
  recreated, and returns `generation_timeout` (504).
- **Gear profile from first principles.** `core/involute.py` computes the tooth outline
  that an ISO 53 basic rack (addendum 1.0 m, dedendum 1.25 m, sharp tip corner) would
  cut: an exact involute flank joined to the trochoid traced by the rack tip, including
  natural undercut below about 21 teeth at 20°. A test compares it with a brute-force
  rack-cutting simulation, and they agree to within about 0.004 mm. Tooth thickness at
  the pitch circle is exactly half the circular pitch (zero backlash).
- **Clearance is a parameter on every part** (default 0.2 mm, diametral). It is added to
  bores and clearance holes and subtracted from male threads. The bearing mount has a
  separate `bearing_clearance` (default 0.1 mm) because press fits want much less.
  Tap holes and heat-set insert holes are not enlarged: they are meant to be undersized.
- **Standoff threads.** Female ends offer tap-size holes, plain clearance holes (spacer)
  or heat-set insert holes rather than modeled internal threads, which print poorly at
  M2 to M3. Male studs are real ISO threads, with a warning below M3.
- **Captive nut traps were left out** as outside the spec (the default agreed during planning).
- **License:** generated files are CC0-1.0, stated in every response. The code is MIT.

## Known limitations

- **GT2 groove profile is an approximation.** Gates does not publish pulley tooth
  geometry. The groove uses the nominal belt tooth (0.75 mm deep, 0.555 mm tip radius,
  1.40 mm wide at the OD) with 0.15 mm land fillets. It works in practice but is not the
  official profile.
- **No gear backlash or profile shift parameters.** Gears are generated at zero backlash.
  Printed gears usually want about 0.1 mm; for now, use slightly negative XY compensation
  in the slicer. Tooth tips are not rounded.
- **Search is keyword and tag matching.** Matching is on whole tokens plus substrings for
  words longer than 3 characters. There is no stemming, synonyms or ranking beyond match
  count.
- **A timeout kills the whole worker pool**, so other jobs running at that moment fail
  with `generation_timeout` too. Queue time counts toward the timeout.
- **Cache has no eviction.** Files accumulate in `data/files` until deleted by hand.
  Deleting a file is safe: it is regenerated on demand from the stored parameters.
- **Bearing mount is narrow.** The base is as wide as the housing (about 9 mm for a 608),
  which suits bolting down but is less stable than a commercial pillow block.
- **Male standoff studs take about 2 seconds** to generate because of thread
  booleans. Everything else is under a second at defaults, though gears with very high
  tooth counts take a few seconds.
- **No authentication or rate limiting.** The server binds to 127.0.0.1 by default. MCP
  DNS-rebinding protection only allows the host given to `--host`.
- **Byte reproducibility depends on library versions.** A different OCCT or lib3mf can
  change file bytes and `file_sha256`, though not the request hash.
- **Previews are flat-shaded matplotlib renders.** They are good enough to eyeball,
  not photorealistic.

## Suggested next steps

1. Gear options: backlash, profile shift, helical gears, and racks that mesh with the
   existing gears.
2. More families: GT2 idlers built on 608/625 bearings, flexible (beam or jaw) couplers,
   T-nuts for 2020 extrusion, knobs and hand wheels, captive nut traps as a shared feature.
3. S3 storage: implement the `Storage` protocol with presigned download URLs, and add
   cache eviction (LRU by last access, tracked in SQLite).
4. Better search: synonyms (sprocket, cog), numeric queries such as "20 tooth module 1
   gear", and returning suggested parameters with search hits.
5. Mating helpers: an operation that returns a matching part (for example "a gear that
   meshes with this one at 40 mm center distance" or "a pillow block for this shaft").
6. Print validation: slice representative parts in CI (PrusaSlicer CLI) to catch
   unprintable features, and keep a log of physical print-and-fit results to tune default
   clearances.
7. Operations: auth tokens, rate limits, a job queue for long generations, and Docker
   packaging.
