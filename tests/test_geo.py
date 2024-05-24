from genio.core.global_components import GlobalComponents


def test_global_components_schedule_can_be_identified():
    components = GlobalComponents.instance()
    for entry in components.schedule.entries:
        assert entry.relevant_location
