VERSION = "2026.0.0"
BUILD_TYPE = "beta.1"
GIT_COMMIT = "190f735"


def get_blender_version_str() -> str:
    """Returns the full version string of the Blender add-on."""

    version_str = VERSION

    # Fallback to the version in the manifest if not set
    if version_str == "":
        import os
        import tomllib

        root_dir = os.path.dirname(os.path.realpath(__file__))
        with open(os.path.join(root_dir, "blender_manifest.toml"), "rb") as f:
            manifest = tomllib.load(f)
            addon_version = manifest.get("version")
            if addon_version is not None:
                version_str = addon_version

    if BUILD_TYPE:
        version_str += f"-{BUILD_TYPE}"
    if GIT_COMMIT:
        version_str += f"+{GIT_COMMIT[:8]}"

    return version_str
