#!/usr/bin/env python3
"""Checks the crows that fly through the main menu sky at the blood moon (INGAME-QS-12 K17). No compile, no game.

The flying crows are the animated crow entities SKY_CROWS of config/mainmenuscene.cfg. The check follows the scene
commands of every crow (AddEntity, ResizeEntity, PosEntity, MoveEntity, Wait) and asserts:

- appear and vanish only out of sight: every place where a crow is put (AddEntity, each PosEntity), stands (Wait)
  or is taken away from lies outside the frame or behind scenery in every view of the menu camera: every Pose of
  [MenuCamera] and dense samples of every flight (outward routes, return routes and the arrival, sampled like
  RenderSceneMenu::samplePath with the slerped rotation). The frame has the horizontal field of view of the widest
  window (32:9) and the vertical one of the narrowest (5:4), so it contains every window of the menu projection.
  A crow counts as out of the frame when its whole bounding sphere lies outside a side plane of the frustum, and as
  behind scenery when the sight lines to its centre and to the six extreme points of that sphere all hit an opaque
  scene triangle first;
- a curved flight is a chain of straight MoveEntity legs whose directions differ by at most MAX_TURN_DEGREES;
- no pop at the far clip or at the sky dome: wherever a crow is in a frame along its flight, it lies nearer than the
  far clip distance and inside the sky dome (the sight line from the overview camera reaches it before the dome);
- the crows still fly at the moon: from Pose overview every crow is in view and unhidden for at least
  MIN_OVERVIEW_SECONDS of its flight and passes within MAX_MOON_DEGREES of the centre of BloodMoon;
- they beat their wings while flying: every flight (MoveEntity) plays the looped Flap clip, and the posed crow mesh
  (bone weights of the mesh, Flap keyframes of the skeleton, skinned like Ogre) shows a wing-beat cycle: over one loop
  each wing tip rises and falls by at least MIN_TIP_STROKE of the half span, the poses differ over time and the loop
  ends in the pose it started with;
- the old sprite swarm MenuCrowSwarm, whose sprites were created and faded inside the visible sky, is not placed.

Fixed values counted once on fix/ingame-qs-12-m2b (six crows; the old scene has no flying crow and the sprite swarm).
Options: --report prints per crow and view where it is seen.

The meshes, skeletons and MenuScene.material live in content packages (found through scripts/content_packages.py);
without the content the check checks the scene commands of the configuration and names the rest as not checked (no
converter is started).
"""
import argparse
import math
import os
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import check_menu_sky_below_horizon as sky  # noqa: E402  (shared mesh reader, poses and flight sampling)
import content_packages  # noqa: E402  (scripts/ is on the path through the menu scene check)

ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
CONFIG = os.path.join(ROOT, "config", "mainmenuscene.cfg")
MODELS = os.path.join(ROOT, "models")
#: The menu scene materials of the public tree or of a content package
MATERIALS = str(content_packages.resolve(ROOT, "materials/scripts/MenuScene.material"))
OUTPUT = os.path.join(ROOT, "out", "menu-sky-crows")
CONVERTER = os.environ.get("OGRE_XML_CONVERTER", "OgreXMLConverter")
#: The flying crows of the moon sky (counted once: six).
SKY_CROWS = ("SkyCrow1", "SkyCrow2", "SkyCrow3", "SkyCrow4", "SkyCrow5", "SkyCrow6")
#: Entities that never hide a crow: the moving crows themselves and the thin distant crow silhouettes (the sky dome
#: materials are left out of every entity; the moon disc BloodMoon stays opaque scenery).
NOT_OCCLUDERS = ("CrowA", "CrowB", "CrowC", "CrowD", "HorizonCrows") + SKY_CROWS
#: Widest supported window aspect (32:9 super-wide screens) and narrowest (5:4, sky.CHECK_ASPECT).
WIDEST_ASPECT = 32.0 / 9.0
#: Flight samples per route segment between two waypoints.
SAMPLES_PER_SEGMENT = 24
#: Spacing in world units of the samples along a crow flight.
PATH_STEP = 1.0
#: Seconds a crow must be in view from Pose overview, and how close (degrees) it must pass the moon centre.
MIN_OVERVIEW_SECONDS = 4.0
MAX_MOON_DEGREES = 12.0
#: Smallest rise and fall of a wing tip over one Flap loop, as a share of the half wingspan.
MIN_TIP_STROKE = 0.5
#: Largest turn in degrees between two straight legs of a curved flight (the crow turns at once at each joint).
MAX_TURN_DEGREES = 8.0
#: Margin added to the crow's bounding sphere (world units) for the out-of-frame and behind-scenery tests.
SPHERE_MARGIN = 0.25


def model_path(name):
    """Returns the mesh or skeleton file of models/ of the public tree or of a content package."""
    return str(content_packages.resolve(ROOT, "models/" + name))


def missing_content(entities):
    """Returns the scene files (MenuScene.material, the meshes of the entities, the skeletons of the flying crows) that
    are not present because the content is not present; empty with the content."""
    if content_packages.has_content(ROOT):
        return []
    needed = ["materials/scripts/MenuScene.material"]
    needed += ["models/" + mesh for mesh in sorted(set(mesh for mesh, _ in entities.values()))]
    needed += ["models/" + os.path.splitext(entities[name][0])[0] + ".skeleton" for name in SKY_CROWS if name in entities]
    return [relative for relative in needed if content_packages.data_file(ROOT, relative) is None]


def parse_scene():
    """Returns (entities {name: (mesh, position)}, scene groups [[command words]], poses, flights)."""
    text = content_packages.read_text(ROOT, "config/mainmenuscene.cfg").replace("\r\n", "\n")
    entities = {}
    groups = []
    for body in re.findall(r"\[RenderSceneGroup\]\n(.*?)\n\[/RenderSceneGroup\]", text, re.S):
        lines = [line.split() for line in body.split("\n") if line.strip() and not line.lstrip().startswith("#")]
        groups.append(lines)
        for words in lines:
            if words[0] == "AddEntity":
                entities[words[1]] = (words[2], np.array([float(v) for v in words[3:6]]))
    _, poses, flights = sky.parse_config()
    return entities, groups, poses, flights, text


def crow_program(name, entities, groups):
    """Returns (scale, stops, flights, turns, problems) of one crow from its scene commands.

    stops are the different positions where the crow appears, stands or vanishes: where it is put (AddEntity,
    PosEntity), where it stands during a Wait and where it is before it is put elsewhere. flights are the different
    (start, end, speed, clip) of its MoveEntity commands in order, each starting where the crow stood before; a crow
    may fly a curve as a chain of MoveEntity legs. turns are the angles in degrees between the directions of two legs
    flown one after the other (MoveEntity turns the crow at once to its next destination).
    """
    problems = []
    position = entities[name][1].copy()
    stops = []
    flights = []
    turns = []
    scale = 1.0

    def stop(point):
        if not any(np.array_equal(point, other) for other in stops):
            stops.append(point.copy())

    stop(position)
    own = [group for group in groups if any(len(w) > 1 and w[1] == name and w[0] != "AddEntity" for w in group)]
    if len(own) != 1:
        return scale, stops, flights, turns, ["%s: needs exactly one scene group with its commands, found %d"
                                              % (name, len(own))]
    group = own[0]
    if ["*Repeat"] not in group:
        problems.append(name + ": its flight must repeat (*Repeat)")
    commands = [words for words in group if words[0] != "*Repeat"]
    # The repeated part runs twice so that the place before its first command is the end of the previous loop.
    repeat = group.index(["*Repeat"]) if ["*Repeat"] in group else len(group)
    loop = [words for words in group[repeat + 1:]]
    previous = None
    for words in commands + loop:
        if words[0] in ("PosEntity", "MoveEntity", "ResizeEntity", "TurnEntity", "AnimationOnce", "AnimationTime")                 and words[1] != name:
            problems.append(name + ": its group drives another entity " + words[1])
        if words[0] == "ResizeEntity":
            scale = float(words[2])
        elif words[0] == "PosEntity":
            stop(position)
            position = np.array([float(v) for v in words[2:5]])
            stop(position)
            previous = None
        elif words[0] == "MoveEntity":
            end = np.array([float(v) for v in words[4:7]])
            direction = (end - position) / np.linalg.norm(end - position)
            if previous is not None:
                turns.append(math.degrees(math.acos(max(-1.0, min(1.0, float(previous @ direction))))))
            previous = direction
            flight = (position.copy(), end, float(words[3]), words[2])
            if not any(np.array_equal(flight[0], other[0]) and np.array_equal(flight[1], other[1]) for other in flights):
                flights.append(flight)
            position = end
        elif words[0] == "Wait":
            stop(position)
            previous = None
        elif words[0] != "*Repeat":
            problems.append(name + ": unexpected command " + words[0])
    if not flights:
        problems.append(name + ": never flies (no MoveEntity)")
    return scale, stops, flights, turns, problems


def camera_views(poses, flights):
    """Returns [(label, position, rotation matrix)] of every pose and dense samples of every menu flight."""
    sky.SAMPLES_PER_SEGMENT = SAMPLES_PER_SEGMENT
    return [(label, position, sky.matrix(orientation)) for label, position, orientation in sky.views(poses, flights)]


def frame_slopes():
    """Returns (tan of the half horizontal, tan of the half vertical field of view) of the containing frame.

    The menu projection (CameraManager::setViewportSize) keeps the vertical field of view of 45 degrees for windows
    of 16:9 and wider, so they see more to the sides, and widens the vertical one for narrower windows. The containing
    frame takes the horizontal extent of the widest window (WIDEST_ASPECT) and the vertical one of the narrowest (5:4).
    """
    half_y = math.atan(math.tan(math.radians(sky.MENU_FOV_Y_DEGREES) * 0.5)
                       * max(1.0, sky.MENU_REFERENCE_ASPECT / sky.CHECK_ASPECT))
    return math.tan(math.radians(sky.MENU_FOV_Y_DEGREES) * 0.5) * WIDEST_ASPECT, math.tan(half_y)


def in_frame(points, position, axes, radius):
    """Returns (touches the frame, depth along the view) for points (n, 3) with a bounding sphere of radius."""
    tan_x, tan_y = frame_slopes()
    offset = points - position
    cx, cy, cz = offset @ axes[:, 0], offset @ axes[:, 1], -(offset @ axes[:, 2])
    inside = cz + radius >= sky.NEAR_CLIP
    for slope, value in ((tan_x, cx), (tan_x, -cx), (tan_y, cy), (tan_y, -cy)):
        inside &= (slope * cz - value) / math.sqrt(1 + slope * slope) >= -radius
    return inside, cz


class Occluders:
    """Opaque scene triangles in spatial cells for sight-line tests, and the sky dome triangles."""

    def __init__(self, entities):
        flags = sky.material_flags(open(MATERIALS, encoding="utf-8").read())
        cache = {}
        opaque = []
        dome = []
        for name, (mesh, position) in entities.items():
            if name in NOT_OCCLUDERS:
                continue
            if mesh not in cache:
                vertices, faces, materials = sky.load_mesh(model_path(mesh))
                materials = np.array(materials)
                blended = np.array([flags.get(m, (False, False))[0] for m in materials], dtype=bool)
                sky_part = np.isin(materials, sky.SKY_MATERIALS)
                keep = ~sky_part & ~np.isin(materials, sky.DECAL_MATERIALS) & ~blended
                cache[mesh] = (vertices[faces[keep]], vertices[faces[np.isin(materials, ("MenuSky",))]])
            solid, sky_triangles = cache[mesh]
            opaque.append(solid + position)
            if len(sky_triangles):
                dome.append(sky_triangles + position)
        triangles = np.concatenate(opaque)
        self.triangles, _, self.starts, self.centres, self.radii = sky.group_chunks(
            triangles, np.zeros(len(triangles), dtype=bool))
        self.dome = np.concatenate(dome) if dome else np.zeros((0, 3, 3))

    @staticmethod
    def _hits(triangles, origin, target):
        """Returns True when the segment origin-target crosses one of the triangles before the target."""
        if len(triangles) == 0:
            return False
        direction = target - origin
        edge1 = triangles[:, 1] - triangles[:, 0]
        edge2 = triangles[:, 2] - triangles[:, 0]
        p = np.cross(direction, edge2)
        det = np.einsum("ij,ij->i", edge1, p)
        usable = np.abs(det) > 1e-12
        inverse = np.where(usable, 1.0 / np.where(usable, det, 1.0), 0.0)
        s = origin - triangles[:, 0]
        u = np.einsum("ij,ij->i", s, p) * inverse
        q = np.cross(s, edge1)
        v = (q @ direction) * inverse
        t = np.einsum("ij,ij->i", edge2, q) * inverse
        return bool(np.any(usable & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 1e-6) & (t < 1 - 1e-6)))

    def hidden(self, origin, target):
        """Returns True when an opaque scene triangle lies on the sight line from origin to target."""
        direction = target - origin
        length = float(np.linalg.norm(direction))
        unit = direction / length
        offset = self.centres - origin
        along = np.clip(offset @ unit, 0.0, length)
        near = np.linalg.norm(offset - along[:, None] * unit, axis=1) <= self.radii + 1e-6
        cells = np.nonzero(near)[0]
        if len(cells) == 0:
            return False
        index = np.concatenate([np.arange(self.starts[c], self.starts[c + 1]) for c in cells])
        return self._hits(self.triangles[index].astype(np.float64), origin, target)

    def beyond_dome(self, origin, target):
        """Returns True when the sky dome lies between origin and target (the target is outside the dome)."""
        return self._hits(self.dome, origin, target)


def sphere_points(centre, radius):
    """Returns the centre and the six extreme points of a sphere."""
    offsets = np.array([[0, 0, 0], [1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1]], dtype=float)
    return centre + offsets * radius


def unseen_problems(label, centre, radius, views, occluders):
    """Returns the views in which a crow put or stopping at centre would be seen (in the frame and not hidden)."""
    seen = []
    for name, position, axes in views:
        inside, _ = in_frame(centre[None, :], position, axes, radius)
        if not inside[0]:
            continue
        if all(occluders.hidden(position, point) for point in sphere_points(centre, radius)):
            continue
        seen.append(name)
    if seen:
        return ["%s at (%.1f, %.1f, %.1f) is seen in %d views, first %s" % (label, centre[0], centre[1], centre[2],
                                                                           len(seen), ", ".join(seen[:4]))]
    return []


def flight_samples(start, end):
    """Returns the sample points of one straight flight, PATH_STEP apart, both ends included."""
    count = max(2, int(math.ceil(np.linalg.norm(end - start) / PATH_STEP)) + 1)
    return start + (end - start) * np.linspace(0.0, 1.0, count)[:, None]


def convert(source, target):
    """Converts an Ogre binary file to XML once per run."""
    subprocess.run([CONVERTER, "-q", source, target], check=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL)


def quaternion_matrix(angle, axis):
    """Returns the rotation matrix of an angle (radians) about an axis."""
    axis = np.asarray(axis, dtype=float)
    norm = np.linalg.norm(axis)
    if norm < 1e-12 or abs(angle) < 1e-12:
        return np.eye(3)
    x, y, z = axis / norm
    c, s = math.cos(angle), math.sin(angle)
    return np.array([[c + x * x * (1 - c), x * y * (1 - c) - z * s, x * z * (1 - c) + y * s],
                     [y * x * (1 - c) + z * s, c + y * y * (1 - c), y * z * (1 - c) - x * s],
                     [z * x * (1 - c) - y * s, z * y * (1 - c) + x * s, c + z * z * (1 - c)]])


def axis_quaternion(angle, axis):
    """Returns the (w, x, y, z) quaternion of an angle (radians) about an axis; identity for a zero axis."""
    axis = np.asarray(axis, dtype=float)
    norm = np.linalg.norm(axis)
    if norm < 1e-12:
        return np.array([1.0, 0.0, 0.0, 0.0])
    return np.concatenate([[math.cos(angle * 0.5)], math.sin(angle * 0.5) * axis / norm])


class Skin:
    """The bind-pose crow mesh with its bone weights and the keyframed clips of its skeleton."""

    def __init__(self, mesh):
        stem = os.path.splitext(mesh)[0]
        os.makedirs(OUTPUT, exist_ok=True)
        mesh_xml = os.path.join(OUTPUT, stem + ".mesh.xml")
        skeleton_xml = os.path.join(OUTPUT, stem + ".skeleton.xml")
        convert(model_path(mesh), mesh_xml)
        convert(model_path(stem + ".skeleton"), skeleton_xml)
        geometry = ET.parse(mesh_xml).getroot()
        rig = ET.parse(skeleton_xml).getroot()
        self.vertices = np.array([[float(p.get(k)) for k in "xyz"] for p in
                                  geometry.findall("./sharedgeometry/vertexbuffer/vertex/position")])
        self.bones = []
        self.bind = {}
        for bone in rig.findall("./bones/bone"):
            name = bone.get("name")
            self.bones.append(name)
            position = bone.find("position")
            rotation = bone.find("rotation")
            axis = rotation.find("axis")
            self.bind[name] = (np.array([float(position.get(k)) for k in "xyz"]),
                               quaternion_matrix(float(rotation.get("angle")), [float(axis.get(k)) for k in "xyz"]))
        self.parent = {link.get("bone"): link.get("parent") for link in rig.findall("./bonehierarchy/boneparent")}
        self.weights = np.zeros((len(self.vertices), len(self.bones)))
        for assignment in geometry.findall("./boneassignments/vertexboneassignment"):
            self.weights[int(assignment.get("vertexindex")), int(assignment.get("boneindex"))] += \
                float(assignment.get("weight"))
        self.clips = {}
        for animation in rig.findall("./animations/animation"):
            tracks = {}
            for track in animation.findall("./tracks/track"):
                keys = []
                for key in track.findall("./keyframes/keyframe"):
                    translate = key.find("translate")
                    rotate = key.find("rotate")
                    move = np.zeros(3) if translate is None else np.array([float(translate.get(k)) for k in "xyz"])
                    turn = (0.0, np.array([1.0, 0.0, 0.0])) if rotate is None else (
                        float(rotate.get("angle")), np.array([float(rotate.find("axis").get(k)) for k in "xyz"]))
                    keys.append((float(key.get("time")), move, turn))
                tracks[track.get("bone")] = keys
            self.clips[animation.get("name")] = (float(animation.get("length")), tracks)

    def _world(self, local):
        """Returns {bone: (position, rotation)} in model space from local (position, rotation) per bone."""
        world = {}

        def resolve(name):
            if name in world:
                return world[name]
            position, rotation = local[name]
            parent = self.parent.get(name)
            if parent is None:
                world[name] = (position, rotation)
            else:
                parent_position, parent_rotation = resolve(parent)
                world[name] = (parent_position + parent_rotation @ position, parent_rotation @ rotation)
            return world[name]

        for name in self.bones:
            resolve(name)
        return world

    def reach(self, clip):
        """Returns the largest distance of a vertex from the entity origin over one loop of a clip."""
        length = self.clips[clip][0]
        return max(float(np.linalg.norm(self.pose(clip, t), axis=1).max()) for t in np.linspace(0.0, length, 17))

    def pose(self, clip, seconds):
        """Returns the skinned vertices of the crow at a time of a clip (keyframes interpolated like Ogre)."""
        length, tracks = self.clips[clip]
        seconds = seconds % length if length > 0 else 0.0
        local = {}
        for name in self.bones:
            position, rotation = self.bind[name]
            keys = tracks.get(name)
            if keys:
                after = next((i for i, key in enumerate(keys) if key[0] >= seconds), len(keys) - 1)
                before = max(after - 1, 0)
                span = keys[after][0] - keys[before][0]
                t = 0.0 if span <= 0 else (seconds - keys[before][0]) / span
                move = keys[before][1] * (1 - t) + keys[after][1] * t
                turn_a = axis_quaternion(keys[before][2][0], keys[before][2][1])
                turn_b = axis_quaternion(keys[after][2][0], keys[after][2][1])
                turn = sky.matrix(sky.slerp(t, turn_a, turn_b))
                position = position + move
                rotation = rotation @ turn
            local[name] = (position, rotation)
        bind = self._world(self.bind)
        posed = self._world(local)
        result = np.zeros_like(self.vertices)
        for index, name in enumerate(self.bones):
            weight = self.weights[:, index]
            if not weight.any():
                continue
            bind_position, bind_rotation = bind[name]
            position, rotation = posed[name]
            moved = ((self.vertices - bind_position) @ bind_rotation) @ rotation.T + position
            result += weight[:, None] * moved
        return result


def wing_beat_problems(mesh, skin):
    """Returns the problems of the Flap wing-beat cycle of one crow mesh."""
    problems = []
    if "Flap" not in skin.clips:
        return [mesh + ": skeleton has no Flap clip"]
    length = skin.clips["Flap"][0]
    times = np.linspace(0.0, length, 17)
    poses = [skin.pose("Flap", t) for t in times[:-1]] + [skin.pose("Flap", 0.0)]
    # The wing tips are the outermost vertices at the widest moment of the beat: a crow may rest with folded wings
    # (the crow figure of CS10a spreads them only in its flight clips), so the rest mesh does not show the tips.
    widest = max(poses, key=lambda pose: pose[:, 0].max() - pose[:, 0].min())
    span = widest[:, 0].max() - widest[:, 0].min()
    left = int(np.argmin(widest[:, 0]))
    right = int(np.argmax(widest[:, 0]))
    end_pose = skin.pose("Flap", length - 1e-4)
    for side, tip in (("left", left), ("right", right)):
        # Height of the tip over the body: the authoring mesh has its up axis along +Z.
        heights = np.array([pose[tip, 2] - pose[:, 2].mean() for pose in poses])
        stroke = heights.max() - heights.min()
        if stroke < MIN_TIP_STROKE * span * 0.5:
            problems.append("%s: %s wing tip rises and falls only %.2f over one Flap loop (needs %.2f)"
                            % (mesh, side, stroke, MIN_TIP_STROKE * span * 0.5))
    distinct = len({tuple(np.round(pose[[left, right]].ravel(), 2)) for pose in poses})
    if distinct < 4:
        problems.append("%s: Flap shows only %d different wing poses" % (mesh, distinct))
    if np.abs(end_pose - poses[0]).max() > 0.05 * span:
        problems.append("%s: Flap does not end in the pose it starts with, the loop jumps" % mesh)
    return problems


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--report", action="store_true", help="print where every crow is seen")
    args = parser.parse_args()
    started = time.monotonic()
    entities, groups, poses, flights, text = parse_scene()
    failures = []
    if re.search(r"(?m)^AddParticleEffect\s+\S+\s+MenuCrowSwarm\b", text):
        failures.append("the sprite swarm MenuCrowSwarm is still placed: its sprites appear and fade inside the sky")
    # The flying crow entities are own rows of the scene configuration: present only with the content
    with_content = content_packages.has_content(ROOT)
    missing = [name for name in SKY_CROWS if name not in entities]
    if missing and with_content:
        failures.append("no flying crow entity " + ", ".join(missing))
    # Without the content only the scene commands above are checked
    absent = missing_content(entities)
    if absent:
        for line in failures:
            print("FAIL " + line)
        content_packages.unchecked("check_menu_sky_crows", absent + ([] if with_content else [
            "flying crow entities (own rows of config/mainmenuscene.cfg)"]))
        return 1 if failures else 0
    views = camera_views(poses, flights)
    overview = [(label, position, axes) for label, position, axes in views if label == "pose overview"]
    occluders = Occluders(entities)
    moon = entities["BloodMoon"][1]
    skins = {}
    print('ODP_TEST_PHASE {"name":"setup","seconds":%.2f}' % (time.monotonic() - started))
    started = time.monotonic()
    for name in SKY_CROWS:
        if name not in entities:
            continue
        mesh = entities[name][0]
        if mesh not in skins:
            skins[mesh] = Skin(mesh)
            failures.extend(wing_beat_problems(mesh, skins[mesh]))
        skin = skins[mesh]
        scale, places, routes, turns, problems = crow_program(name, entities, groups)
        if turns and max(turns) > MAX_TURN_DEGREES:
            failures.append("%s turns by %.1f degrees at once between two legs (at most %.1f)"
                            % (name, max(turns), MAX_TURN_DEGREES))
        failures.extend(problems)
        radius = scale * skin.reach("Flap") + SPHERE_MARGIN
        for place in places:
            failures.extend(unseen_problems(name + " stop", place, radius, views, occluders))
        seen_seconds = 0.0
        moon_angle = 180.0
        for start, end, speed, clip in routes:
            if clip != "Flap":
                failures.append("%s flies with %s instead of the looped Flap wing beat" % (name, clip))
            samples = flight_samples(start, end)
            step = float(np.linalg.norm(end - start)) / max(len(samples) - 1, 1)
            for label, position, axes in views:
                inside, depth = in_frame(samples, position, axes, radius)
                if np.any(inside & (depth + radius > sky.FAR_CLIP)):
                    failures.append("%s passes the far clip inside the frame of %s" % (name, label))
            outside_dome = [point for point in samples[::4] if occluders.beyond_dome(overview[0][1], point)]
            if outside_dome:
                point = outside_dome[0]
                failures.append("%s flies outside the sky dome at (%.1f, %.1f, %.1f)" % (name, point[0], point[1], point[2]))
            _, position, axes = overview[0]
            inside, _ = in_frame(samples, position, axes, -radius)
            for point in samples[inside]:
                if not occluders.hidden(position, point):
                    seen_seconds += step / speed
                    sight = (point - position) / np.linalg.norm(point - position)
                    towards = (moon - position) / np.linalg.norm(moon - position)
                    moon_angle = min(moon_angle, math.degrees(math.acos(min(1.0, float(sight @ towards)))))
            if args.report:
                for label, position, axes in views:
                    inside, _ = in_frame(samples, position, axes, radius)
                    if inside.any():
                        print("%s seen from %s on %d of %d samples" % (name, label, inside.sum(), len(samples)))
        if seen_seconds < MIN_OVERVIEW_SECONDS:
            failures.append("%s is in view from Pose overview for %.1f s only (needs %.1f)"
                            % (name, seen_seconds, MIN_OVERVIEW_SECONDS))
        if moon_angle > MAX_MOON_DEGREES:
            failures.append("%s passes the moon no closer than %.1f degrees (needs %.1f)"
                            % (name, moon_angle, MAX_MOON_DEGREES))
        print("%s: scale %.2f, %d flights, %.1f s in the overview, %.1f degrees from the moon"
              % (name, scale, len(routes), seen_seconds, moon_angle))
    print('ODP_TEST_PHASE {"name":"test","seconds":%.2f}' % (time.monotonic() - started))
    for line in failures:
        print("FAIL " + line)
    if failures:
        return 1
    print("OK: %d sky crows appear and vanish only out of the frame or behind scenery in %d menu views and beat their "
          "wings" % (len(SKY_CROWS), len(views)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
