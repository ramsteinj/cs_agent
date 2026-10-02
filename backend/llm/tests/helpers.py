def run(gen):
    """Drain a stream_reply generator: (deltas, FinalReply)."""
    deltas = []
    while True:
        try:
            deltas.append(next(gen))
        except StopIteration as stop:
            return deltas, stop.value
