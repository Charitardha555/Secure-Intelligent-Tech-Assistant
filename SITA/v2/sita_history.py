import os
from datetime import datetime

HISTORY_DIR = os.path.join(os.path.dirname(__file__), 'history')

class SessionHistory:
    def __init__(self):
        if not os.path.exists(HISTORY_DIR):
            os.makedirs(HISTORY_DIR)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.file_path = os.path.join(HISTORY_DIR, f'session_{timestamp}.txt')
        self.history = []
        with open(self.file_path, 'w', encoding='utf-8') as f:
            f.write('')

    def append(self, role, message):
        entry = f'{role}: {message}\n'
        self.history.append(entry)
        with open(self.file_path, 'a', encoding='utf-8') as f:
            f.write(entry)

    def get_history(self):
        return ''.join(self.history)

# Usage example (to be integrated in your AI logic):
# session = SessionHistory()
# session.append('User', 'Hello!')
# session.append('AI', 'Hi, how can I help you?')
# context = session.get_history()
