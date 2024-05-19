from genio.core.agent import Agent


def test_agent_can_have_context():
    agent = Agent()
    assert agent.context() is not None
