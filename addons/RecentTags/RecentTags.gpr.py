# ------------------------------------------------------------------------
# RecentTags.gpr.py — Gramps plugin registration
# ------------------------------------------------------------------------

from gramps.version import major_version

register(
    GENERAL,
    id    = "RecentTags",
    name  = "Recent Tags",
    description = (
        "Remembers recently used tags and shows them at the top of the "
        "Edit Tag List dialog for quick access."
    ),
    version = "0.1.0",
    gramps_target_version = major_version,
    status = EXPERIMENTAL,
    fname  = "RecentTags.py",
    load_on_reg = True,
    authors = ["Claude AI (https://claude.ai)", "Kari Kujansuu"],
    authors_email = ["kari.kujansuu@gmail.com"],
)

register(
    TOOL,
    id         = "RecentTagsPrefs",
    name       = _("Recent Tags Preferences"),
    description= _("Configure the Recent Tags addon."),
    version    = "0.1.0",
    gramps_target_version = major_version,
    status     = EXPERIMENTAL,
    fname      = "RecentTags.py",
    authors = ["Claude AI ((https://claude.ai)", "Kari Kujansuu"],
    authors_email = ["kari.kujansuu@gmail.com"],
    category   = TOOL_UTILS,
    toolclass  = "RecentTagsPreferencesTool",
    optionclass = "RecentTagsOptions",
)
