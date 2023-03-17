from __future__ import annotations

import json
import os
import pathlib

from globus_sdk.tokenstorage import SQLiteAdapter

from .._environments import _get_envname
from .client_login import get_client_login, is_client_login
from .globus_auth import internal_auth_client


def _home() -> pathlib.Path:
    # this is a hook point for tests to patch over
    # it just returns `pathlib.Path.home()`
    # replace this with a mock to return some test directory
    return pathlib.Path.home()


def invalidate_old_config() -> None:
    token_file = _home() / ".globus_compute" / "credentials" / "funcx_sdk_tokens.json"

    if token_file.exists():
        try:
            auth_client = internal_auth_client()
            with open(token_file) as fp:
                data = json.load(fp)
            for token_data in data.values():
                if "access_token" in token_data:
                    auth_client.oauth2_revoke_token(token_data["access_token"])
                if "refresh_token" in token_data:
                    auth_client.oauth2_revoke_token(token_data["refresh_token"])
        finally:
            os.remove(token_file)


def _ensure_funcx_dir() -> pathlib.Path:
    legacy_dirname = _home() / ".funcx"
    dirname = _home() / ".globus_compute"

    try:
        if os.path.exists(legacy_dirname) and os.path.isdir(legacy_dirname):
            # If the legacy dir (.funcx) already exists, create a symlink
            os.symlink(legacy_dirname, dirname, target_is_directory=True)

        elif os.path.islink(dirname) and not os.path.exists(dirname):
            # If the symlink is broken, remove it and create a fresh dir
            os.unlink(dirname)
            os.makedirs(dirname)

        else:
            # Otherwise, just create the dir
            os.makedirs(dirname)
    except FileExistsError:
        pass

    return dirname


def _get_storage_filename():
    datadir = _ensure_funcx_dir()
    return os.path.join(datadir, "storage.db")


def _resolve_namespace(environment: str | None) -> str:
    """
    Return the namespace used to save tokens. This will check
    if a client login is being used and return either:
      user/<envname>
    or
      clientprofile/<envname>/<clientid>

    e.g.

      user/production
    """
    env = environment if environment is not None else _get_envname()

    if is_client_login():
        client_id = get_client_login().client_id
        return f"clientprofile/{env}/{client_id}"

    return f"user/{env}"


def get_token_storage_adapter(*, environment: str | None = None) -> SQLiteAdapter:
    # when initializing the token storage adapter, check if the storage file exists
    # if it does not, then use this as a flag to clean the old config
    fname = _get_storage_filename()
    if not os.path.exists(fname):
        invalidate_old_config()
    # namespace is equal to the current environment
    return SQLiteAdapter(
        fname,
        namespace=_resolve_namespace(environment),
        connect_params={"check_same_thread": False},
    )
