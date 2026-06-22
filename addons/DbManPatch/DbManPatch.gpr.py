from gramps.version import major_version


register(
    GENERAL,
    id="DbManPatch",
    name=_("DbManPatch"),
    description=_("DbManPatch"),
    version="0.0.1",
    gramps_target_version=major_version,
    status=STABLE,
    fname="DbManPatch.py",
    load_on_reg=True,
)

