from genio.core.global_components import GlobalComponents
from icecream import ic

components = GlobalComponents.instance()
for entry in components.schedule.entries:
    ic(entry.relevant_location)
