"""Questions the solver cannot express. The parser must refuse them, not invent a scene.

Each category writes three phrasings (textbook, casual, terse) with random numbers. The target
output is ``{"unsupported": "<category>"}``. These are *my own* problems in each category; none is
copied from a user's test list or a textbook.

Categories are things the scene format genuinely lacks: vectors and resultants, relative motion,
two bodies meeting, pulleys and connected bodies, apparent weight, spring combinations, static
spring extension, circular motion, calculus-defined motion, motion with no mass, inverse problems,
energy methods, momentum, rotation, and non-mechanics questions.
"""

from __future__ import annotations

import random
from collections.abc import Callable

from .phrasing import fmt, pick

Texts = tuple[str, str, str]  # textbook, casual, terse


def _vector_sum(rng: random.Random) -> Texts:
    a, b, ang = (
        pick(rng, [5, 8, 10, 12, 20]),
        pick(rng, [6, 9, 15, 16]),
        pick(rng, [30, 45, 60, 90]),
    )
    return (
        f"Two forces of {a} N and {b} N act on a point object, with an angle of {ang} degrees between them. "
        f"Find the magnitude and direction of the resultant force.",
        f"I've got a {a} N pull and a {b} N pull on a ring, {ang} degrees apart. What's the combined force?",
        f"Forces {a} N and {b} N, {ang} deg apart. Resultant magnitude and direction?",
    )


def _displacements(rng: random.Random) -> Texts:
    a, b = pick(rng, [4, 6, 8, 10]), pick(rng, [3, 5, 7, 12])
    return (
        f"A walker goes {a} km east and then {b} km north. Determine the magnitude and direction of "
        f"the total displacement.",
        f"I walked {a} km east then turned and walked {b} km north. How far am I from the start, and in what direction?",
        f"{a} km east, then {b} km north. Net displacement magnitude and direction.",
    )


def _dot_cross(rng: random.Random) -> Texts:
    p = [pick(rng, [1, 2, 3, 4, -1, -2]) for _ in range(6)]
    va = f"{p[0]}i + {p[1]}j + {p[2]}k"
    vb = f"{p[3]}i + {p[4]}j + {p[5]}k"
    return (
        f"Given the vectors A = {va} and B = {vb}, calculate A dot B and A cross B.",
        f"If A = {va} and B = {vb}, what are the dot product and cross product?",
        f"A = {va}, B = {vb}. Dot and cross products.",
    )


def _river(rng: random.Random) -> Texts:
    v, u, w = pick(rng, [3, 4, 5, 6]), pick(rng, [1, 2, 3]), pick(rng, [60, 100, 120, 200])
    return (
        f"A boat moves at {v} m/s relative to the water in a river that flows at {u} m/s. It heads "
        f"straight across a river {w} m wide. How long does the crossing take and how far downstream does it drift?",
        f"My boat does {v} m/s in still water, the river runs at {u} m/s and is {w} m wide. "
        f"If I aim straight across, how long until I'm over and how far downstream do I land?",
        f"Boat {v} m/s vs water, current {u} m/s, width {w} m, aimed across: time and drift.",
    )


def _overtake(rng: random.Random) -> Texts:
    va, vb, gap, acc = (
        pick(rng, [20, 25, 30]),
        pick(rng, [10, 15, 18]),
        pick(rng, [50, 80, 100]),
        pick(rng, [1, 2, 3]),
    )
    return (
        f"Car A drives at a constant {va} m/s. Car B starts {gap} m behind it at {vb} m/s and speeds up at "
        f"{acc} m/s^2. When and where does B catch A?",
        f"One car is cruising at {va} m/s. Another is {gap} m back doing {vb} m/s and accelerating at "
        f"{acc} m/s^2. When does the second one catch up?",
        f"A: {va} m/s constant. B: {gap} m behind, {vb} m/s, a = {acc} m/s^2. Catch-up time and place?",
    )


def _atwood(rng: random.Random) -> Texts:
    a, b = pick(rng, [2, 3, 4]), pick(rng, [5, 6, 8])
    return (
        f"Masses of {a} kg and {b} kg hang from the two ends of a light string over a smooth pulley. "
        f"Find the acceleration of the masses and the tension in the string.",
        f"There's a {a} kg weight and a {b} kg weight on either side of a frictionless pulley. How fast "
        f"do they accelerate and what's the string tension?",
        f"Atwood machine, {a} kg and {b} kg. Acceleration and tension.",
    )


def _elevator(rng: random.Random) -> Texts:
    m, a = pick(rng, [50, 60, 70, 80]), pick(rng, [1, 1.5, 2, 3])
    return (
        f"A {m} kg person stands on a bathroom scale in an elevator that accelerates upward at {fmt(a)} m/s^2. "
        f"What does the scale read?",
        f"I weigh {m} kg and I'm in a lift going up with an acceleration of {fmt(a)} m/s^2. "
        f"What force does the scale show?",
        f"{m} kg person, elevator up at {fmt(a)} m/s^2, scale reading?",
    )


def _connected(rng: random.Random) -> Texts:
    a, b, c, f = pick(rng, [2, 3]), pick(rng, [3, 4]), pick(rng, [5, 6]), pick(rng, [30, 40, 50])
    return (
        f"Three blocks of {a} kg, {b} kg and {c} kg are joined in a line by light strings on a smooth floor. "
        f"A {f} N horizontal force pulls the {c} kg block. Find the acceleration and the tension in each string.",
        f"Blocks of {a}, {b} and {c} kg are tied together in a row on a smooth table and I pull the {c} kg "
        f"one with {f} N. What are the acceleration and the string tensions?",
        f"{a} kg - {b} kg - {c} kg on strings, smooth floor, {f} N on the {c} kg block: a and tensions.",
    )


def _series_springs(rng: random.Random) -> Texts:
    k1, k2, f = pick(rng, [100, 150, 200]), pick(rng, [200, 300, 400]), pick(rng, [20, 30, 40])
    return (
        f"Springs with constants {k1} N/m and {k2} N/m are connected in series and a force of {f} N acts "
        f"on the combination. Find the equivalent spring constant and the total extension.",
        f"I hooked a {k1} N/m spring to a {k2} N/m spring end to end and pull with {f} N. "
        f"What's the effective spring constant and how far does it stretch?",
        f"Springs {k1} and {k2} N/m in series, {f} N applied: k_eq and extension.",
    )


def _parallel_springs(rng: random.Random) -> Texts:
    k1, k2, m = pick(rng, [100, 150]), pick(rng, [200, 300]), pick(rng, [4, 6, 9])
    return (
        f"Two springs of constants {k1} N/m and {k2} N/m are connected in parallel and hold up a {m} kg mass. "
        f"Find the equilibrium extension and the force from each spring.",
        f"A {m} kg mass hangs from two side-by-side springs, {k1} N/m and {k2} N/m. "
        f"How much do they stretch and what does each spring pull with?",
        f"Parallel springs {k1}, {k2} N/m, {m} kg hanging: extension, force in each.",
    )


def _hooke(rng: random.Random) -> Texts:
    k, f = pick(rng, [100, 200, 250, 500]), pick(rng, [10, 20, 30, 50])
    return (
        f"A spring with spring constant {k} N/m is pulled by a force of {f} N. By how much does it stretch?",
        f"How far does a {k} N/m spring stretch when I pull it with {f} N?",
        f"k = {k} N/m, pulled with {f} N: extension?",
    )


def _hanging_spring(rng: random.Random) -> Texts:
    m, k = pick(rng, [2, 3, 5, 8]), pick(rng, [100, 200, 250])
    return (
        f"A {m} kg mass hangs at rest from a vertical spring of spring constant {k} N/m. "
        f"Determine the extension of the spring.",
        f"I hung a {m} kg weight from a {k} N/m spring. How much longer does the spring get?",
        f"{m} kg hanging on a {k} N/m spring, extension at equilibrium?",
    )


def _circular(rng: random.Random) -> Texts:
    m, r, v = pick(rng, [1, 2, 3]), pick(rng, [1, 1.5, 2, 3]), pick(rng, [4, 6, 8])
    return (
        f"A {m} kg object on a string of length {fmt(r)} m moves in a horizontal circle at a constant "
        f"speed of {v} m/s. Find the centripetal acceleration and the centripetal force.",
        f"I'm swinging a {m} kg ball on a {fmt(r)} m string in a circle at {v} m/s. "
        f"How big is the centripetal force?",
        f"{m} kg, radius {fmt(r)} m, speed {v} m/s, circular: centripetal a and F.",
    )


def _curve(rng: random.Random) -> Texts:
    m, r, mu = pick(rng, [800, 1000, 1200]), pick(rng, [50, 80, 100]), pick(rng, [0.4, 0.5, 0.6])
    return (
        f"A {m} kg car goes around a flat circular curve of radius {r} m. The coefficient of static friction "
        f"between the tyres and the road is {fmt(mu)}. What is the maximum speed without skidding?",
        f"How fast can a {m} kg car take a flat bend of radius {r} m if the tyre friction coefficient is {fmt(mu)}?",
        f"Flat curve r = {r} m, mu_s = {fmt(mu)}, {m} kg car: max speed.",
    )


def _vertical_circle(rng: random.Random) -> Texts:
    m, r, v = pick(rng, [0.3, 0.5, 1]), pick(rng, [0.8, 1, 1.5]), pick(rng, [5, 6, 7])
    return (
        f"A {fmt(m)} kg ball on a string of length {fmt(r)} m moves in a vertical circle. Find the minimum "
        f"speed at the top, and the tension at the bottom if its speed there is {v} m/s.",
        f"I whirl a {fmt(m)} kg ball on a {fmt(r)} m string in a vertical loop. What's the slowest it can go "
        f"at the top, and how much is the tension at the bottom at {v} m/s?",
        f"Vertical circle, {fmt(m)} kg, r = {fmt(r)} m: min speed at top; tension at bottom for {v} m/s.",
    )


def _calculus(rng: random.Random) -> Texts:
    c, t = pick(rng, [2, 3, 4, 6]), pick(rng, [2, 3, 4, 5])
    return (
        f"A particle starts from rest and has acceleration a = {c}t (SI units). Find its velocity and "
        f"displacement after {t} seconds.",
        f"A particle's acceleration is {c}t m/s^2 and it starts at rest. What are its velocity and position at t = {t} s?",
        f"a = {c}t, from rest. v and x at t = {t} s.",
    )


def _inverse(rng: random.Random) -> Texts:
    m, a = pick(rng, [2, 5, 10, 20]), pick(rng, [1, 2, 3])
    return (
        f"What constant horizontal force must act on a {m} kg block on a smooth floor to give it an "
        f"acceleration of {a} m/s^2?",
        f"How hard do I need to push a {m} kg crate on ice to make it accelerate at {a} m/s^2?",
        f"{m} kg on smooth floor, a = {a} m/s^2: force needed?",
    )


def _inverse_mu(rng: random.Random) -> Texts:
    m, v, d = pick(rng, [20, 50, 100]), pick(rng, [10, 15, 20]), pick(rng, [20, 30, 50])
    return (
        f"A {m} kg crate sliding at {v} m/s comes to rest after {d} m on a horizontal floor. "
        f"Find the coefficient of kinetic friction.",
        f"A {m} kg crate slides {d} m before stopping from {v} m/s. What's the friction coefficient?",
        f"{m} kg, {v} m/s, stops in {d} m: mu_k?",
    )


def _start_force(rng: random.Random) -> Texts:
    m, mu = pick(rng, [2, 5, 10, 20]), pick(rng, [0.3, 0.4, 0.5, 0.6])
    return (
        f"A {m} kg crate rests on a horizontal floor with a static friction coefficient of {fmt(mu)}. "
        f"What is the smallest horizontal force that will make it start to move?",
        f"How hard do I have to push a {m} kg box before it budges? The floor's static friction "
        f"coefficient is {fmt(mu)}.",
        f"{m} kg on a floor, mu_s = {fmt(mu)}: minimum force to start it moving.",
    )


def _start_extension(rng: random.Random) -> Texts:
    m, k, mu = pick(rng, [1, 2, 3]), pick(rng, [50, 100, 200]), pick(rng, [0.3, 0.4, 0.5])
    return (
        f"A {m} kg block is attached to a spring of constant {k} N/m on a horizontal surface where the "
        f"coefficient of static friction is {fmt(mu)}. The spring is stretched slowly. How far must it be "
        f"stretched before the block begins to slide?",
        f"I'm slowly pulling a {m} kg block with a {k} N/m spring across a table (mu_s = {fmt(mu)}). "
        f"At what stretch does it start to slip?",
        f"{m} kg, spring {k} N/m, mu_s {fmt(mu)}: stretch at which it starts sliding?",
    )


def _slip_angle(rng: random.Random) -> Texts:
    m, mu = pick(rng, [1, 2, 5, 8]), pick(rng, [0.3, 0.5, 0.6, 0.8])
    return (
        f"A {m} kg block sits on a board whose angle is slowly increased. The coefficient of static friction "
        f"is {fmt(mu)}. At what angle does the block start to slide?",
        f"I'm tilting a plank with a {m} kg block on it (mu_s = {fmt(mu)}). How steep before it slips?",
        f"{m} kg block on a tilting board, mu_s {fmt(mu)}: angle at which it starts to slide.",
    )


def _position_polynomial(rng: random.Random) -> Texts:
    a, b, c, d = (
        pick(rng, [1, 2, 3]),
        pick(rng, [6, 9, 12, 15]),
        pick(rng, [12, 18, 24]),
        pick(rng, [2, 5, 8]),
    )
    t = pick(rng, [4, 5, 6])
    return (
        f"The position of a particle on the x-axis is x(t) = {a}t^3 - {b}t^2 + {c}t + {d} (metres, seconds). "
        f"During the first {t} seconds, when does it reverse direction and what total distance does it cover?",
        f"A bug's position along a line is x = {a}t^3 - {b}t^2 + {c}t + {d}. Over the first {t} s, "
        f"when does it turn around and how far does it travel in total?",
        f"x(t) = {a}t^3 - {b}t^2 + {c}t + {d}, 0 to {t} s: turning instants, total distance.",
    )


def _growing_deceleration(rng: random.Random) -> Texts:
    u, c = pick(rng, [10, 15, 20, 30]), pick(rng, [0.2, 0.4, 0.5, 1])
    return (
        f"A tram moving at {u} m/s starts braking with a deceleration that grows steadily with time, "
        f"a = {fmt(c)}t (SI units). When does it stop and how far does it go?",
        f"A tram doing {u} m/s brakes harder and harder: deceleration = {fmt(c)} times the elapsed seconds. "
        f"How long until it stops, and how far?",
        f"u = {u} m/s, a = -{fmt(c)}t: stop time and stopping distance.",
    )


def _two_projectiles(rng: random.Random) -> Texts:
    v, a1, a2 = pick(rng, [20, 25, 30, 40]), pick(rng, [30, 35, 40]), pick(rng, [50, 55, 60])
    return (
        f"Two stones are thrown at the same time from level ground, both at {v} m/s, one at {a1} degrees and "
        f"the other at {a2} degrees above the horizontal. Find the difference between their maximum heights "
        f"and how far apart they are horizontally when the first one lands.",
        f"I throw two stones together at {v} m/s, one {a1} degrees up and one {a2} degrees up. By how much do "
        f"their peak heights differ, and how far apart are they when the first hits the ground?",
        f"Two stones, {v} m/s, {a1} deg and {a2} deg, same start: height difference; separation at first landing.",
    )


def _against_wall(rng: random.Random) -> Texts:
    m, f, ang, mu = (
        pick(rng, [2, 4, 5]),
        pick(rng, [60, 80, 100]),
        pick(rng, [15, 20, 30]),
        pick(rng, [0.3, 0.4, 0.5]),
    )
    return (
        f"A {m} kg block is pressed against a vertical wall by a force of {f} N directed {ang} degrees above the "
        f"horizontal. The coefficient of static friction is {fmt(mu)}. What are the normal force and the "
        f"friction force, and does the block stay at rest?",
        f"I'm holding a {m} kg block on a wall, pushing with {f} N at {ang} degrees upward (mu_s = {fmt(mu)}). "
        f"Will it slide down? What are the normal and friction forces?",
        f"{m} kg against a wall, {f} N at {ang} deg above horizontal, mu_s {fmt(mu)}: forces, does it slip?",
    )


def _largest_at_rest(rng: random.Random) -> Texts:
    m, k, f, mu = (
        pick(rng, [2, 3, 4]),
        pick(rng, [100, 150, 200]),
        pick(rng, [20, 30, 40]),
        pick(rng, [0.3, 0.4, 0.5]),
    )
    return (
        f"A {m} kg block on a rough floor (static friction coefficient {fmt(mu)}) is joined to a wall by a spring "
        f"of constant {k} N/m. A {f} N horizontal force pulls it away from the wall. What is the largest "
        f"extension at which the block can still stay at rest?",
        f"A {m} kg block is tied to a wall by a {k} N/m spring and pulled with {f} N along a floor with "
        f"mu_s = {fmt(mu)}. How far can the spring stretch while the block holds still?",
        f"{m} kg, spring {k} N/m, pull {f} N, mu_s {fmt(mu)}: largest stretch with the block at rest.",
    )


def _rough_then_smooth(rng: random.Random) -> Texts:
    m, k, x, d, mu = (
        pick(rng, [1, 2, 3]),
        pick(rng, [200, 400, 500]),
        pick(rng, [0.1, 0.15, 0.2]),
        pick(rng, [0.3, 0.5, 0.8]),
        pick(rng, [0.1, 0.2, 0.3]),
    )
    return (
        f"A {m} kg block is released from a spring ({k} N/m) compressed by {fmt(x)} m. For the first {fmt(d)} m "
        f"of its path the floor is rough (kinetic friction coefficient {fmt(mu)}) and after that it is smooth. "
        f"How fast is it moving once it reaches the smooth part?",
        f"A spring ({k} N/m, compressed {fmt(x)} m) fires a {m} kg block across {fmt(d)} m of rough floor "
        f"(mu_k = {fmt(mu)}) and then onto ice. What is its speed on the ice?",
        f"{m} kg, spring {k} N/m compressed {fmt(x)} m, rough for {fmt(d)} m (mu_k {fmt(mu)}) then smooth: speed on smooth part.",
    )


def _max_compression(rng: random.Random) -> Texts:
    m, v, d, mu, k = (
        pick(rng, [1, 2, 3]),
        pick(rng, [5, 6, 8]),
        pick(rng, [0.5, 1, 2]),
        pick(rng, [0.1, 0.2, 0.3]),
        pick(rng, [300, 500, 800]),
    )
    return (
        f"A {m} kg block slides at {v} m/s along a rough floor (kinetic friction coefficient {fmt(mu)}) toward "
        f"a spring of constant {k} N/m that is {fmt(d)} m away. How far is the spring compressed at most?",
        f"A {m} kg puck is shot at {v} m/s over {fmt(d)} m of rough floor (mu_k = {fmt(mu)}) into a {k} N/m spring. "
        f"What is the maximum compression?",
        f"{m} kg at {v} m/s, {fmt(d)} m to a {k} N/m spring, mu_k {fmt(mu)}: maximum compression.",
    )


def _spring_energy(rng: random.Random) -> Texts:
    m, k, x = pick(rng, [1, 2, 3]), pick(rng, [200, 400, 500]), pick(rng, [0.1, 0.15, 0.2])
    return (
        f"A {m} kg block compresses a spring of constant {k} N/m by {fmt(x)} m on a frictionless floor "
        f"and is released. What is its speed when the spring reaches its natural length?",
        f"I push a {m} kg block into a {k} N/m spring by {fmt(x)} m and let go. How fast is it moving when the spring "
        f"is back to normal length?",
        f"{m} kg, spring {k} N/m compressed {fmt(x)} m: speed at natural length.",
    )


def _collision(rng: random.Random) -> Texts:
    m1, v1, m2 = pick(rng, [2, 3, 4]), pick(rng, [4, 6, 8]), pick(rng, [1, 2, 3])
    return (
        f"A {m1} kg cart moving at {v1} m/s hits a {m2} kg cart at rest and the two stick together. "
        f"Find their common velocity.",
        f"A {m1} kg trolley at {v1} m/s crashes into a stationary {m2} kg trolley and they lock together. How fast do they move?",
        f"{m1} kg at {v1} m/s hits {m2} kg at rest, stick: final velocity.",
    )


def _rotation(rng: random.Random) -> Texts:
    m, r, tau = pick(rng, [2, 5, 10]), pick(rng, [0.2, 0.5]), pick(rng, [3, 5, 8])
    return (
        f"A solid disk of mass {m} kg and radius {fmt(r)} m is spun by a torque of {tau} N m. "
        f"Find its angular acceleration.",
        f"A {m} kg uniform disk of radius {fmt(r)} m gets a {tau} N m torque. How quickly does it speed up its spin?",
        f"Disk {m} kg, r = {fmt(r)} m, torque {tau} N m: angular acceleration.",
    )


def _not_mechanics(rng: random.Random) -> Texts:
    q = pick(
        rng,
        [
            "What is the capital of France?",
            "Write a short poem about autumn.",
            "Solve x^2 - 5x + 6 = 0.",
            "How do I convert a Python list to a set?",
            "What is the boiling point of water at sea level in kelvin?",
            "Explain what a black hole is.",
        ],
    )
    return (q, q, q)


CATEGORIES: dict[str, Callable[[random.Random], Texts]] = {
    "vector addition": _vector_sum,
    "vector displacement": _displacements,
    "dot or cross product": _dot_cross,
    "relative motion": _river,
    "two bodies meeting": _overtake,
    "pulley or connected bodies": _atwood,
    "apparent weight": _elevator,
    "connected bodies": _connected,
    "springs in series": _series_springs,
    "springs in parallel": _parallel_springs,
    "static spring extension": _hooke,
    "hanging spring": _hanging_spring,
    "circular motion": _circular,
    "banked or flat curve": _curve,
    "vertical circle": _vertical_circle,
    "calculus motion": _calculus,
    "find the force from the motion": _inverse,
    "find the friction from the motion": _inverse_mu,
    "threshold force to start moving": _start_force,
    "threshold stretch to start sliding": _start_extension,
    "threshold angle to start sliding": _slip_angle,
    "position as a function of time": _position_polynomial,
    "deceleration that changes with time": _growing_deceleration,
    "two projectiles compared": _two_projectiles,
    "block pressed against a wall": _against_wall,
    "largest value at rest": _largest_at_rest,
    "rough then smooth floor": _rough_then_smooth,
    "maximum spring compression": _max_compression,
    "energy method": _spring_energy,
    "momentum or collision": _collision,
    "rotation": _rotation,
    "not a mechanics problem": _not_mechanics,
}


def make(rng: random.Random) -> tuple[str, dict[str, str]]:
    """A category and its three phrasings."""
    category = pick(rng, sorted(CATEGORIES))
    textbook, casual, terse = CATEGORIES[category](rng)
    return category, {"textbook": textbook, "casual": casual, "terse": terse}
