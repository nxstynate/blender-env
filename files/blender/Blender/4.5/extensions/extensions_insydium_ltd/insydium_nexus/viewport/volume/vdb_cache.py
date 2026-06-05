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

"""OpenVDB cache writer for nxExplosiaFX volume data.

Writes per-frame ``.vdb`` file containing density and temperature grids
fetched from Theron, for consumption by Blender's Volume datablock
(and rendered by Cycles and Eevee).

Used by ``handlers/render.py``.

Flat layout from Theron (matches ``viewport/volume/basic.py``):
    flat[iz*ny*nx + iy*nx + ix]   - x is the fastest-varying axis
Here we reshape to ``(nz, ny, nx)`` and transpose to ``(nx, ny, nz)`` for
OpenVDB's ``copyFromArray`` (which iterates ``array[i, j, k] -> grid (i, j, k)``).

Note on module name: In Blender 5.0 the OpenVDB Python binding is ``openvdb``.
In older Blender versions it is named ``pyopenvdb``. The two APIs are the same, so
use an import helper to try both names when importing the module.
"""

from __future__ import annotations

import os

import numpy as np


def _import_openvdb():
    """Return the OpenVDB Python module, regardless of name."""
    for name in ("openvdb", "pyopenvdb"):
        try:
            return __import__(name)
        except ImportError:
            continue
    return None


def _flat_to_xyz_array(flat_data, resolution) -> np.ndarray:
    """Convert a Theron ctypes flat array to a contiguous ``(nx, ny, nz)`` float32 array."""
    nx, ny, nz = resolution
    arr_zyx = np.frombuffer(flat_data, dtype=np.float32, count=nx * ny * nz).reshape(nz, ny, nx)
    return np.ascontiguousarray(arr_zyx.transpose(2, 1, 0))


def _build_grid_transform(vdb, resolution, voxel_size):
    """Linear transform that places voxel centers symmetrically around the modifier origin."""
    nx, ny, nz = resolution
    v = float(voxel_size)
    ox = -(nx - 1) * v * 0.5
    oy = -(ny - 1) * v * 0.5
    oz = -(nz - 1) * v * 0.5
    matrix = (
        (v, 0.0, 0.0, 0.0),
        (0.0, v, 0.0, 0.0),
        (0.0, 0.0, v, 0.0),
        (ox, oy, oz, 1.0),
    )
    return vdb.createLinearTransform(matrix=matrix)


def _set_fog_class(grid, vdb) -> None:
    """Attempt to tag the grid as a fog volume."""
    cls = getattr(vdb, "GRID_FOG_VOLUME", None)
    if cls is None:
        return
    try:
        grid.gridClass = cls
    except (AttributeError, TypeError):
        pass


def _set_voxel_class(grid, vdb) -> None:
    """Attempt to tag the grid as a voxel volume."""
    cls = getattr(vdb, "GRID_VOXEL_VOLUME", None)
    if cls is None:
        return
    try:
        grid.gridClass = cls
    except (AttributeError, TypeError):
        pass


def write_efx_vdb_blank(filepath: str) -> bool:
    """Write a VDB containing empty density and temperature grids.

    Used for frames where Theron has no simulation data yet (e.g. the reset
    frame). Cycles and Eevee read this as "no volume" and render
    nothing — which is what we want when scrubbing back to the start.

    The grids carry no active voxels, so transform / voxel size are
    irrelevant; just preserve the grid names so the linked material resolves correctly.
    """
    tag = "[nx_explosiafx vdb_cache]"
    vdb = _import_openvdb()
    if vdb is None:
        print(f"{tag} no OpenVDB Python binding available.")
        return False

    grids = []
    for name in ("density", "temperature"):
        g = vdb.FloatGrid()
        g.name = name
        if name == "temperature":
            _set_voxel_class(g, vdb)
        else:
            _set_fog_class(g, vdb)
        grids.append(g)

    parent_dir = os.path.dirname(filepath)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)

    vdb.write(filepath, grids)
    return True


def write_efx_vdb(
    modifier_handle: int,
    filepath: str,
    ambient_temperature: float = 0.0,
) -> bool:
    """Write density + temperature grids for one ExplosiaFX modifier to ``filepath``.

    The voxel size for each grid is taken from the channel-fetch return — the
    engine-side value, which may differ from the user-set value. Different channels
    are permitted to carry different values (e.g., future support for mixing upres and base
    channels in the same VDB file). Each grid gets its own transform.

    Channels that are disabled in Theron are omitted from the VDB file.
    ShaderNodeAttribute defaults missing attributes to zero when sampled, so
    materials work without changes with channels present or omitted.

    Returns True on success. Returns False when no field is available (e.g.,
    Theron not running, frame 1 with no data yet, pyopenvdb missing, both
    channels disabled). The caller can then skip rendering this modifier
    without aborting the whole render.
    """
    tag = "[nx_explosiafx vdb_cache]"
    vdb = _import_openvdb()
    if vdb is None:
        print(f"{tag} no OpenVDB Python binding available.")
        return False

    from ...libs import theron

    if modifier_handle is None:
        print(f"{tag} modifier_handle is None — skipping write")
        return False
    if not theron.is_initialized():
        print(f"{tag} theron not initialized — skipping write")
        return False

    # Fetch base-resolution channels independently. A None return means the
    # channel is disabled in the backend, then it is omitted from the VDB rather than
    # failing the whole write.
    smoke_result = theron.get_efx_smoke_field(modifier_handle)
    temp_result = theron.get_efx_temperature_field(modifier_handle)

    # Reject bad resolutions (treat as missing channel) but keep the other channel.
    if smoke_result is not None and any(n <= 0 for n in smoke_result[1]):
        print(f"{tag} non-positive smoke resolution {smoke_result[1]}")
        smoke_result = None
    if temp_result is not None and any(n <= 0 for n in temp_result[1]):
        print(f"{tag} non-positive temp resolution {temp_result[1]}")
        temp_result = None

    if smoke_result is None and temp_result is None:
        print(f"{tag} smoke and temperature both unavailable — skipping write")
        return False

    # Build base-resolution grids per available channel.
    density_grid = None
    if smoke_result is not None:
        smoke_flat, smoke_resolution, smoke_dx = smoke_result
        smoke_transform = _build_grid_transform(vdb, smoke_resolution, smoke_dx)
        density_arr = _flat_to_xyz_array(smoke_flat, smoke_resolution)
        density_grid = vdb.FloatGrid()
        density_grid.copyFromArray(density_arr)
        density_grid.transform = smoke_transform
        density_grid.name = "density"
        _set_fog_class(density_grid, vdb)

    temperature_grid = None
    if temp_result is not None:
        temp_flat, temp_resolution, temp_dx = temp_result
        temp_transform = _build_grid_transform(vdb, temp_resolution, temp_dx)
        temperature_arr = _flat_to_xyz_array(temp_flat, temp_resolution)
        # Setting background = ambient lets OpenVDB collapse all bit-equal voxel values into
        # inactive and save space.
        temperature_grid = vdb.FloatGrid(ambient_temperature)
        temperature_grid.copyFromArray(temperature_arr)
        temperature_grid.transform = temp_transform
        temperature_grid.name = "temperature"
        _set_voxel_class(temperature_grid, vdb)

    # Dynamic grid list: upscaled grids take the default material-attribute
    # names ("density" / "temperature") and lead the list IF they are available. In
    # that case the base-resolution grids are appended to the end with "_baseres" label suffix.
    # This means that the highest quality grid will be selected automatically by renderers.
    # When upres is unavailable for a channel, the base grid keeps the default name and the
    # back list gets no entry for that channel. Channels with no base data at all
    # contribute nothing to the file.
    front_grids: list = []
    back_grids: list = []

    # Smoke channel — only attempt upres if the base channel exists.
    if density_grid is not None:
        smokeUpres_result = theron.get_efx_field_upres(
            modifier_handle, theron.TrEFXChannel.TR_EFX_CHANNEL_SMOKE
        )
        if smokeUpres_result is not None:
            smokeUpres_flat, smokeUpres_resolution, smokeUpres_dx = smokeUpres_result
            smokeUpres_transform = _build_grid_transform(vdb, smokeUpres_resolution, smokeUpres_dx)
            densityUpres_arr = _flat_to_xyz_array(smokeUpres_flat, smokeUpres_resolution)

            densityUpres_grid = vdb.FloatGrid()
            densityUpres_grid.copyFromArray(densityUpres_arr)
            densityUpres_grid.transform = smokeUpres_transform
            densityUpres_grid.name = "density"
            _set_fog_class(densityUpres_grid, vdb)

            # Demote the baseres so the upres takes the default "density" name.
            density_grid.name = "density_baseres"
            front_grids.append(densityUpres_grid)
            back_grids.append(density_grid)
        else:
            front_grids.append(density_grid)

    # Temperature channel — as above...
    if temperature_grid is not None:
        tempUpres_result = theron.get_efx_field_upres(
            modifier_handle, theron.TrEFXChannel.TR_EFX_CHANNEL_TEMPERATURE
        )
        if tempUpres_result is not None:
            tempUpres_flat, tempUpres_resolution, tempUpres_dx = tempUpres_result
            tempUpres_transform = _build_grid_transform(vdb, tempUpres_resolution, tempUpres_dx)
            tempUpres_arr = _flat_to_xyz_array(tempUpres_flat, tempUpres_resolution)

            tempUpres_grid = vdb.FloatGrid()
            tempUpres_grid.copyFromArray(tempUpres_arr)
            tempUpres_grid.transform = tempUpres_transform
            tempUpres_grid.name = "temperature"
            _set_voxel_class(tempUpres_grid, vdb)

            # Demote the baseres so the upres takes the default "temperature" name.
            temperature_grid.name = "temperature_baseres"
            front_grids.append(tempUpres_grid)
            back_grids.append(temperature_grid)
        else:
            front_grids.append(temperature_grid)

    parent_dir = os.path.dirname(filepath)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)

    vdb.write(filepath, front_grids + back_grids)
    return True
