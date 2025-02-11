from gramps.version import major_version

register(GRAMPLET,
     id="Family ChildMerge",
     name=_("Family ChildMerge"),
     description = _("Gramplet showing the children of a family and allowing to merge them"),
     version="1.0.0",
     gramps_target_version=major_version,
     status = STABLE,
     fname="ChildMerge.py",
     height=200,
     gramplet = 'FamilyChildMerge',
     gramplet_title=_("ChildMerge"),
     navtypes=["Family"],
)


register(
    GENERAL,
    id="Embedded-ChildMerge",
    name=_("Embedded-ChildMerge"),
    description=_("Embedded ChildMerge"),
    version="0.9.0",
    gramps_target_version=major_version,
    status=STABLE,
    fname="Embedded-ChildMerge.py",
    load_on_reg=True,
)


#    register(GRAMPLET,
#         id="Person ChildMerge",
#         name=_("Person ChildMerge"),
#         description = _("Gramplet showing the children of a person and allowing to merge them"),
#         version="1.0.0",
#         gramps_target_version=major_version,
#         status = STABLE,
#         fname="ChildMerge.py",
#         height=200,
#         gramplet = 'PersonChildMerge',
#         gramplet_title=_("ChildMerge"),
#         navtypes=["Person"],
#    )
