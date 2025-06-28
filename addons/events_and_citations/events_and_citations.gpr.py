from gramps.version import major_version

register(GRAMPLET,
    id="Person Events and Citations",
    name=_("Person Events and Citations"),
    description = _("Gramplet showing the events and attached citations for a person"),
    version="1.0.1",
    target_version=major_version,
    status=EXPERIMENTAL,
    fname="events_and_citations.py",
    height=200,
    gramplet = 'Person_Events_and_Citations',
    gramplet_title=_("Events and Citations"),
    navtypes=["Person"],
)


