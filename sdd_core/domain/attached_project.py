#!/usr/bin/env python3
"""
Facade domain model for target project attachments.
Delegates to modularized sub-domain files (FIX-017).
"""

from __future__ import annotations

from sdd_core.domain.attachment_domain import (
    DEFAULT_ATTACHMENT_PATH,
    DEFAULT_ATTACHMENTS_DIR,
    DEFAULT_ATTACHMENT_REGISTRY_PATH,
    DEFAULT_WORKSPACE_PATH,
    COMPONENT_ROOT_FIELDS,
    COMPONENT_RESERVED_FIELDS,
    ATTACHMENT_ROOT_FIELDS,
    ATTACHMENT_RESERVED_FIELDS,
    ATTACHMENT_STATE_FIELDS,
    RISK_TIERS_REQUIRING_VERIFICATION_COMMANDS,
    normalize_path,
    normalize_candidate_path,
    normalize_root_list,
    sanitize_profile_name,
    sanitize_bucket_name,
    build_profile_project_id,
    default_scan_roots,
    default_schema_roots,
    is_fixture_attachment,
    build_attachment_project_id,
    build_attachment_profile_name,
    validate_components_for_risk_tier,
)
from sdd_core.domain.attachment_service import (
    build_component_payload,
    normalize_components,
    collect_component_roots,
    normalize_attachment_payload,
    component_id_for_path,
    resolve_module_map_scan_settings,
    source_signature,
    build_attachment_payload,
    normalize_attachment_json,
)
from sdd_core.domain.attachment_io import (
    get_config_repository,
    set_config_repository,
    attachments_dir_for,
    attachment_profiles_dir_for,
    attachment_registry_path_for,
    workspace_path_for,
    write_attachment_json,
    build_workspace_payload,
    refresh_workspace_file,
    attachment_store_lock_path,
    load_attachment_config,
    save_attachment_config,
    load_attachment_seed,
    remove_attachment_profile,
    set_active_attachment_profile,
    list_attachment_profiles,
)
