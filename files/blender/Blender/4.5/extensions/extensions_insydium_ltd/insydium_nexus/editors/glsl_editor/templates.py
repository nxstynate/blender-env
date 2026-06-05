# INSYDIUM NeXus Add-on for Blender
# Copyright (C) 2026 INSYDIUM LTD
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""GLSL code templates for the NeXus particle script editor.

Each template is a ``(name, description, code)`` tuple.  The code uses
the Theron property-based API (``particle.*``, ``doc.*``, etc.).
"""

GLSL_TEMPLATES: list[tuple[str, str, str]] = [
    # ------------------------------------------------------------------
    (
        "Empty",
        "Minimal starting point",
        """\
void main()
{

}
""",
    ),
    # ------------------------------------------------------------------
    (
        "Color by Speed",
        "Slow particles appear blue, fast particles appear red",
        """\
void main()
{
    // normalize speed to 0-1 range; adjust the multiplier to suit your particle velocities
    float speed = clamp(particle.speed * 0.2, 0.0, 1.0);
    // slow = blue, fast = red
    particle.color = vec3(speed, 0.0, 1.0 - speed);
}
""",
    ),
    # ------------------------------------------------------------------
    (
        "Fade Color Over Lifetime",
        "Particle color fades from orange to blue over its lifetime",
        """\
void main()
{
    // 0.0 at birth, 1.0 at end of life
    float lifeRatio = particle.age / particle.life;
    // blend from orange to blue
    particle.color = mix(vec3(1.0, 0.5, 0.0), vec3(0.0, 0.2, 1.0), lifeRatio);
}
""",
    ),
    # ------------------------------------------------------------------
    (
        "Orbit Force",
        "Push particles tangentially around the world origin in the XZ plane",
        """\
void main()
{
    // flatten to XZ plane to orbit around the Y axis
    vec3 pos = vec3(particle.position.x, 0.0, particle.position.z);
    float dist = length(pos);
    if (dist > 0.001)
    {
        // tangent is perpendicular to the radial direction and the Y axis
        vec3 tangent = cross(normalize(pos), vec3(0.0, 1.0, 0.0));
        // doc.delta makes the force frame-rate independent
        particle.velocity += tangent * 300.0 * doc.delta;
    }
}
""",
    ),
    # ------------------------------------------------------------------
    (
        "Color Cycling by Distance Travelled",
        "Cycle through the color wheel based on accumulated distance using particle.smoke",
        """\
void main()
{
    // accumulate distance travelled; particle.smoke persists between frames
    particle.smoke += particle.speed * doc.delta;

    // mod() cycles the value without needing a reset
    float t = mod(particle.smoke, 200.0) / 200.0;

    // three sin waves offset by 120 degrees cycle smoothly through the color wheel
    particle.color = vec3(
        sin(t * 6.28318) * 0.5 + 0.5,
        sin(t * 6.28318 + 2.09440) * 0.5 + 0.5,
        sin(t * 6.28318 + 4.18879) * 0.5 + 0.5
    );
}
""",
    ),
    # ------------------------------------------------------------------
    (
        "Spawn Child Particle on Birth",
        "Spawn a smaller child particle from the parent's position when it is born",
        """\
void main()
{
    // particle.born is true only on the frame the particle is created
    if (particle.born)
    {
        emitter[0].create(
            particle.position,
            particle.velocity + vec3(0.0, 50.0, 0.0),  // inherit velocity plus upward offset
            vec3(1.0, 0.8, 0.0),                        // orange
            particle.radius * 0.5,                       // half the parent radius
            particle.life * 0.5,                         // half the parent lifespan
            0,                                           // flags (always 0)
            0                                            // userdata
        );
    }
}
""",
    ),
    # ------------------------------------------------------------------
    (
        "Animated Vector Field",
        "Steer particles along flowing organic paths with a time-animated trig field",
        """\
void main()
{
    // scale position into field space
    float scale = 0.004;
    vec3 p = particle.position * scale;
    // animate the field over time
    float t = doc.time * 0.3;

    // each component uses offset axes to prevent the field aligning to a single direction
    vec3 field = vec3(
        cos(p.y + t) - sin(p.z + t),
        cos(p.z + t) - sin(p.x + t),
        cos(p.x + t) - sin(p.y + t)
    );

    particle.velocity += field * 200.0 * doc.delta;
    // map field direction to color
    particle.color = abs(normalize(field));
}
""",
    ),
    # ------------------------------------------------------------------
    (
        "Expanding Shockwave",
        "A wave front pulses outward from the origin, pushing particles radially as it passes",
        """\
void main()
{
    float waveSpeed = 400.0;  // units per second
    float wavePeriod = 3.0;   // seconds between pulses
    float waveWidth = 40.0;   // sharpness of the pulse edge

    // current radius of the wave front
    float waveRadius = mod(doc.time, wavePeriod) * waveSpeed;
    float dist = length(particle.position);
    // Gaussian falloff centered on the wave front
    float wave = exp(-pow(dist - waveRadius, 2.0) / (waveWidth * waveWidth));

    if (dist > 0.001)
    {
        // push particles outward proportional to wave intensity
        particle.velocity += normalize(particle.position) * wave * 2000.0 * doc.delta;
    }

    // blend from dark base color to bright orange at the wave front
    particle.color = mix(vec3(0.05, 0.05, 0.1), vec3(1.0, 0.6, 0.1), wave);
}
""",
    ),
    # ------------------------------------------------------------------
    (
        "Sphere Surface Flow",
        "Attract particles to a sphere surface and push them tangentially around it",
        """\
void main()
{
    // set this to match the scale of your emitter
    float targetRadius = 300.0;
    float dist = length(particle.position);

    if (dist > 0.001)
    {
        vec3 normal = particle.position / dist;

        // attract toward the sphere surface; strength scales with distance from it
        particle.velocity += normal * (targetRadius - dist) * 3.0 * doc.delta;

        // push tangentially to create surface flow around the Y axis
        vec3 tangent = cross(normal, vec3(0.0, 1.0, 0.0));
        particle.velocity += tangent * 200.0 * doc.delta;

        // cyan on the surface, orange when far from it
        float t = clamp(abs(dist - targetRadius) / 100.0, 0.0, 1.0);
        particle.color = mix(vec3(0.2, 0.8, 1.0), vec3(1.0, 0.2, 0.0), t);
    }
}
""",
    ),
]
