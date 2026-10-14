# Architecture

Scene JSON (givens only) -> validate -> solve per segment -> Timeline -> viewer.

- The solver assigns contact/connection regimes, solves one linear system per segment for accelerations and
  constraint forces, finds the next event (stop, edge, slack, slide start), and starts a new segment.
- Constant-acceleration segments use closed-form motion; RK4 is used only for non-constant forces (springs).
- `Timeline.at(t)` is a pure lookup, so scrubbing backward works.
- Internal units are SI, Y up, right-handed, vectors `[x, y, z]`.

Detailed schema and solver notes are added as each milestone lands.
