class CallState:
    def __init__(self):
        self.history: list[str] = []  # user/agent turn alternados

    def user_turn(self, text: str):
        self.history.append(text)

    def agent_turn(self, text: str):
        self.history.append(text)

def init() -> CallState:
    return CallState()