"""Catharsis as a dynamical system.

One tick of the field is a linear map followed by a clamp:

    x  <-  clamp( (I - diag(DECAY) + COUPLING) x )

so the per-edge dynamics are an affine discrete-time system, and everything the
subject supplies -- spectra, fixed points, saddles, separatrices, basins,
bifurcations -- is available exactly rather than by simulation.

Two honest caveats about what "exactly" covers.

*The full runtime is not this map.*  Action selection is an ``argmax`` over
pressures, which partitions the state space into cells; inside a cell the
dynamics are affine, and at the boundaries they switch.  Catharsis is therefore
a **piecewise-affine hybrid system**, and its bifurcations are *border
collisions* -- a fixed point crossing an action threshold and a behaviour
switching on -- rather than the pitchforks and Hopf bifurcations of smooth
theory.  What is computed here is the within-cell part, which is the part that
governs how a relationship drifts between events.

*The dimension is not fixed.*  Memories accumulate, so the true state space
grows.  Phase portraits below are therefore slices: two axes of one edge, with
everything else held where it is.

Nothing here needs a numerical library; the eigensolver is a plain QR iteration.
"""

from __future__ import annotations

import cmath
from dataclasses import dataclass
from dataclasses import field as dc_field
from functools import cache

from .field import COUPLING, DECAY, EMOTIONS

Matrix = list[list[float]]

#: How close to the unit circle counts as neither growing nor decaying.
MARGINAL = 1e-3


# ----------------------------------------------------------------------------
# the operator
# ----------------------------------------------------------------------------
def linear_operator(axes: tuple[str, ...] = EMOTIONS) -> Matrix:
    """One tick of the field, restricted to ``axes``, as a matrix.

    Restricting is a projection, not a different model: the sub-matrix is what
    the full system does when the omitted axes are zero and stay zero.
    """
    index = {name: i for i, name in enumerate(axes)}
    size = len(axes)
    matrix = [[0.0] * size for _ in range(size)]
    for i, name in enumerate(axes):
        matrix[i][i] = 1.0 - DECAY[name]
    for source, target, rate in COUPLING:
        if source in index and target in index:
            matrix[index[target]][index[source]] += rate
    return matrix


# ----------------------------------------------------------------------------
# spectrum
# ----------------------------------------------------------------------------
def _qr(matrix: Matrix) -> tuple[Matrix, Matrix]:
    """Gram-Schmidt QR.  Small matrices only, which is all we ever have."""
    size = len(matrix)
    q = [[0.0] * size for _ in range(size)]
    r = [[0.0] * size for _ in range(size)]
    columns = [[matrix[row][col] for row in range(size)] for col in range(size)]
    for j in range(size):
        v = columns[j][:]
        for i in range(j):
            qi = [q[row][i] for row in range(size)]
            r[i][j] = sum(qi[row] * columns[j][row] for row in range(size))
            for row in range(size):
                v[row] -= r[i][j] * qi[row]
        norm = sum(value * value for value in v) ** 0.5
        r[j][j] = norm
        for row in range(size):
            q[row][j] = v[row] / norm if norm > 1e-14 else 0.0
    return q, r


def eigenvalues(matrix: Matrix, iterations: int = 3000) -> list[complex]:
    """Eigenvalues, largest modulus first, via unshifted QR iteration."""
    size = len(matrix)
    if size == 1:
        return [complex(matrix[0][0])]
    current = [row[:] for row in matrix]
    for _ in range(iterations):
        q, r = _qr(current)
        current = [[sum(r[i][k] * q[k][j] for k in range(size)) for j in range(size)] for i in range(size)]
    found: list[complex] = []
    i = 0
    while i < size:
        if i + 1 < size and abs(current[i + 1][i]) > 1e-8:
            a, b = current[i][i], current[i][i + 1]
            c, d = current[i + 1][i], current[i + 1][i + 1]
            trace, det = a + d, a * d - b * c
            root = cmath.sqrt(complex(trace * trace - 4 * det))
            found += [(trace + root) / 2, (trace - root) / 2]
            i += 2
        else:
            found.append(complex(current[i][i]))
            i += 1
    found.sort(key=lambda z: (-abs(z), -z.real))
    return found


def dominant_mode(matrix: Matrix, iterations: int = 4000) -> tuple[float, list[float]]:
    """Growth factor per tick and the direction that grows, by power iteration."""
    size = len(matrix)
    vector = [1.0] * size
    growth = 0.0
    for _ in range(iterations):
        nxt = [sum(matrix[i][j] * vector[j] for j in range(size)) for i in range(size)]
        growth = max(abs(value) for value in nxt) or 1.0
        vector = [value / growth for value in nxt]
    return growth, vector


# ----------------------------------------------------------------------------
# classification
# ----------------------------------------------------------------------------
@dataclass
class Spectrum:
    axes: tuple[str, ...]
    values: list[complex]
    growth: float
    mode: list[float]
    #: Growth of the fastest-growing direction that is actually *reachable* --
    #: see :func:`feasible_growth`.  This, not the spectral radius, is the number
    #: that says whether a Catharsis field runs away.
    reachable: float = 0.0
    reachable_mode: list[float] = dc_field(default_factory=list)

    @property
    def radius(self) -> float:
        return abs(self.values[0]) if self.values else 0.0

    @property
    def unstable(self) -> list[complex]:
        return [z for z in self.values if abs(z) > 1.0 + MARGINAL]

    @property
    def stable(self) -> list[complex]:
        return [z for z in self.values if abs(z) < 1.0 - MARGINAL]

    @property
    def oscillating(self) -> list[complex]:
        return [z for z in self.values if abs(z.imag) > 1e-9]

    @property
    def kind(self) -> str:
        """How the origin of this subsystem behaves, in the linear picture."""
        if not self.values:
            return "empty"
        if self.unstable and self.stable:
            return "saddle"
        if self.unstable:
            return "source"
        if all(abs(z) < 1.0 - MARGINAL for z in self.values):
            return "sink"
        return "marginal"

    @property
    def runs_away(self) -> bool:
        """Whether anything the runtime can actually reach grows without bound."""
        return self.reachable > 1.0 + MARGINAL

    @property
    def verdict(self) -> str:
        linear = {
            "saddle": "saddle",
            "source": "source",
            "sink": "sink",
            "marginal": "marginal",
            "empty": "empty",
        }[self.kind]
        if self.runs_away:
            return (
                f"RUNS AWAY — linearly a {linear} (rho {self.radius:.4f}), and the "
                f"instability is reachable: feasible growth {self.reachable:.4f}/tick"
            )
        if self.unstable:
            return (
                f"HELD BY THE CONE — linearly a {linear} (rho {self.radius:.4f}), but every "
                "growing eigenvector needs a negative emotion, so nothing reaches it"
            )
        return f"SETTLES — {linear} (rho {self.radius:.4f}); everything decays to indifference"

    def reachable_dominant(self, limit: int = 6, floor: float = 0.02) -> list[tuple[str, float]]:
        pairs = [
            (name, value)
            for name, value in zip(self.axes, self.reachable_mode, strict=True)
            if abs(value) >= floor
        ]
        pairs.sort(key=lambda pair: -abs(pair[1]))
        return pairs[:limit]

    def dominant(self, limit: int = 6, floor: float = 0.02) -> list[tuple[str, float]]:
        """The axes making up the fastest-growing direction."""
        pairs = [
            (name, value) for name, value in zip(self.axes, self.mode, strict=True) if abs(value) >= floor
        ]
        pairs.sort(key=lambda pair: -abs(pair[1]))
        return pairs[:limit]

    def period(self, value: complex) -> float | None:
        phase = abs(cmath.phase(value))
        return (2 * cmath.pi / phase) if phase > 1e-9 else None


def feasible_growth(matrix: Matrix, iterations: int = 5000) -> tuple[float, list[float]]:
    """Growth of the best direction an emotion vector is allowed to point in.

    Charges cannot be negative, so the state space is the non-negative orthant
    and not all of R^n.  An eigenvector with a negative component therefore names
    a mode the runtime can never enter, and the spectral radius can be larger
    than anything reachable.  This projects onto the cone at every step, which
    is what the runtime's clamp does, and reports what actually grows.
    """
    size = len(matrix)
    vector = [1.0] * size
    growth = 0.0
    for _ in range(iterations):
        nxt = [max(0.0, sum(matrix[i][j] * vector[j] for j in range(size))) for i in range(size)]
        growth = max(nxt) or 1.0
        vector = [value / growth for value in nxt]
    return growth, vector


@cache
def spectrum(axes: tuple[str, ...] = EMOTIONS) -> Spectrum:
    """The eigen-picture of one subsystem.

    Cached: the field constants do not change at runtime, so this is a pure
    function of ``axes`` -- and it is not cheap, since the twenty-axis case runs
    3000 QR iterations.  `catharsis spectrum -o` asks for the whole field twice,
    once for the printed verdict and once inside the page.  Callers read the
    result and never mutate it.
    """
    matrix = linear_operator(axes)
    growth, mode = dominant_mode(matrix)
    reachable, reachable_mode = feasible_growth(matrix)
    return Spectrum(tuple(axes), eigenvalues(matrix), growth, mode, reachable, reachable_mode)


@cache
def drivers(axes: tuple[str, ...] = EMOTIONS, limit: int = 6) -> list[tuple[float, str, str, float]]:
    """Which couplings the instability is made of.

    Each is removed in turn and the spectral radius recomputed, so the number is
    that coupling's actual contribution rather than its size.
    """
    index = {name: i for i, name in enumerate(axes)}
    base_matrix = linear_operator(axes)
    base = dominant_mode(base_matrix, iterations=1500)[0]
    out = []
    for source, target, rate in COUPLING:
        if source not in index or target not in index:
            continue
        perturbed = [row[:] for row in base_matrix]
        perturbed[index[target]][index[source]] -= rate
        out.append((base - dominant_mode(perturbed, iterations=1500)[0], source, target, rate))
    out.sort(reverse=True)
    return out[:limit]


# ----------------------------------------------------------------------------
# a 2D slice: phase portrait, separatrix, basins
# ----------------------------------------------------------------------------
@dataclass
class Portrait:
    """Everything needed to draw a two-axis slice of one edge."""

    axes: tuple[str, str]
    spectrum: Spectrum
    field: list[dict] = dc_field(default_factory=list)
    manifolds: list[dict] = dc_field(default_factory=list)
    basins: list[list[int]] = dc_field(default_factory=list)
    corners: list[dict] = dc_field(default_factory=list)
    resolution: int = 0
    grid: int = 0


def _step(matrix: Matrix, point: list[float]) -> list[float]:
    size = len(point)
    out = [sum(matrix[i][j] * point[j] for j in range(size)) for i in range(size)]
    return [0.0 if v < 0.0 else 1.0 if v > 1.0 else v for v in out]


def _settle(matrix: Matrix, point: list[float], steps: int = 6000) -> list[float]:
    """Iterate to the attractor, with the two short-cuts that make it affordable.

    Decay in this field can be as slow as 0.5% a tick, so a fixed step budget
    reports points that are merely *on their way* to the origin as if they were
    attractors of their own.  Both exits below are exact rather than heuristic:
    once every axis is at the clamp the state cannot move, and once the whole
    vector is tiny and still shrinking the origin is the only place left.
    """
    for _ in range(steps):
        nxt = _step(matrix, point)
        if all(abs(a - b) < 1e-12 for a, b in zip(nxt, point, strict=True)):
            return nxt
        if max(nxt) < 1e-4 and sum(nxt) <= sum(point):
            return [0.0] * len(point)
        point = nxt
    return point


def portrait(axes: tuple[str, str], resolution: int = 17, grid: int = 61) -> Portrait:
    """A phase portrait for two emotional axes on a single edge.

    ``field`` is the displacement one tick produces, sampled on a coarse grid.
    ``basins`` labels each point of a finer grid by where it ends up, so the
    separatrix appears as the boundary between labels rather than being drawn.
    """
    matrix = linear_operator(axes)
    spec = spectrum(axes)
    out = Portrait(axes=axes, spectrum=spec, resolution=resolution, grid=grid)

    for row in range(resolution):
        for col in range(resolution):
            x = col / (resolution - 1)
            y = row / (resolution - 1)
            nxt = _step(matrix, [x, y])
            out.field.append({"x": x, "y": y, "dx": nxt[0] - x, "dy": nxt[1] - y})

    # eigenvectors give the invariant lines through the origin
    for value in spec.values:
        if abs(value.imag) > 1e-9:  # pragma: no cover - see TestNothingOscillates
            # A complex pair spirals, and a spiral has no invariant line to
            # draw.  No slice of the actual field reaches this: every pair of
            # the twenty axes comes out with real eigenvalues, so every slice is
            # a node or a saddle and none is a centre.
            continue
        lam = value.real
        a, b = matrix[0][0], matrix[0][1]
        # A vertical eigendirection has no slope; report it as absent rather
        # than as infinity, which is not representable in JSON.
        slope = (lam - a) / b if abs(b) > 1e-12 else None
        out.manifolds.append(
            {
                "eigenvalue": lam,
                "slope": slope,
                "kind": "unstable" if abs(lam) > 1.0 + MARGINAL else "stable",
            }
        )

    labels: dict[tuple[int, int], int] = {}
    ends: list[tuple[float, float]] = []
    for row in range(grid):
        line = []
        for col in range(grid):
            end = _settle(matrix, [col / (grid - 1), row / (grid - 1)])
            key = (round(end[0], 1), round(end[1], 1))
            if key not in labels:
                labels[key] = len(ends)
                ends.append((end[0], end[1]))
            line.append(labels[key])
        out.basins.append(line)
    out.corners = [{"x": x, "y": y, "index": i} for i, (x, y) in enumerate(ends)]
    return out


# ----------------------------------------------------------------------------
# bifurcation: sweep a parameter, watch where the system ends up
# ----------------------------------------------------------------------------
def sweep(
    axes: tuple[str, str],
    start: tuple[float, float],
    along: int = 0,
    steps: int = 81,
) -> list[dict]:
    """Vary one starting coordinate and record where the slice settles.

    A jump in the output is a border collision: the initial condition has
    crossed the separatrix and the system now falls into the other basin.
    """
    matrix = linear_operator(axes)
    out = []
    for i in range(steps):
        value = i / (steps - 1)
        point = list(start)
        point[along] = value
        end = _settle(matrix, point[:])
        out.append({"parameter": value, "x": end[0], "y": end[1]})
    return out


# ----------------------------------------------------------------------------
# bifurcation of the whole runtime, not just the field
# ----------------------------------------------------------------------------
def runtime_bifurcation(template: str, steps: int = 41, low: float = 0.0, high: float = 1.0) -> list[dict]:
    """Run a whole program repeatedly, varying one number, and record the outcome.

    This is where Catharsis' interesting bifurcations actually live.  The field
    on its own is affine and boring: either it decays to indifference or it
    saturates.  What switches is *behaviour* -- an action's pressure crosses the
    threshold and an agent starts doing something it was not doing before -- and
    that is a border collision, invisible to the linear analysis above.

    ``template`` is program source in which every ``{}`` is replaced by the
    swept value, so one sweep can move several lines at once.
    """
    from .parser import parse
    from .world import World

    out = []
    for i in range(steps):
        value = low + (high - low) * i / (steps - 1)
        world = World()
        # replace, not format: a template may need the same value in several places
        world.run(parse(template.replace("{}", f"{value:.4f}")))
        bonds = [bond for agent in world.agents.values() for bond in agent.others()]
        acts = sum(1 for event in world.log if event.kind == "act")
        groups = list(world.groups.values())
        out.append(
            {
                "parameter": value,
                "trust": (sum(b.get("trust") for b in bonds) / len(bonds)) if bonds else 0.0,
                "grievance": (sum(b.get("resentment") + b.get("doubt") for b in bonds) / len(bonds))
                if bonds
                else 0.0,
                "actions": acts,
                "progress": (groups[0].progress / groups[0].required)
                if groups and groups[0].required
                else 0.0,
                "achieved": bool(groups and groups[0].achieved_at is not None),
            }
        )
    return out


# ----------------------------------------------------------------------------
# a real run, projected onto the slice
# ----------------------------------------------------------------------------
def trajectory(world, source: str, target: str, axes: tuple[str, str]) -> list[dict]:
    """Where an actual program went, in the coordinates of a phase portrait.

    Requires a recorded world (``World(record=True)``), which is what makes the
    theory and the examples land in the same picture.
    """
    path = []
    for frame in world.frames:
        agent = frame["state"]["agents"].get(source)
        if not agent:
            continue
        bond = agent["bonds"].get(target)
        if not bond:
            # The edge does not exist yet -- or never does, if the caller named
            # one that is not there.  Either way there is no point to plot, and
            # inventing one puts a false line through the origin.
            continue
        charge = bond["charge"]
        path.append(
            {
                "tick": frame["tick"],
                "label": frame["label"],
                "x": charge.get(axes[0], 0.0),
                "y": charge.get(axes[1], 0.0),
            }
        )
    return path
