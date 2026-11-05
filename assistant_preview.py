"""Experimental product with session memory, trace readback and referenced arithmetic."""
from memory_chat import Chat as MemoryChat
from explicit_command_chat import ExplicitCommands
from reference_ops_chat import Chat as ReferenceChat
from trace_readback_chat import selected_readback
from followon_product_chat import Chat as FollowonChat
from reference_ops_chat import accepted_patterns


class PreviewBackend(ExplicitCommands, ReferenceChat):
    """Honor the preview's optional reader injection without changing scored modes."""
    def __init__(self,model,tok,guard,reader=None):
        if reader is None:
            super().__init__(model,tok,guard)
            return
        FollowonChat.__init__(self,model,tok,guard,reader=reader)
        self.readback=selected_readback()
        self.readback_answer=None
        self.patterns=accepted_patterns()
        self.reference_call=False
        self.reference_notice=None


class Chat(MemoryChat):
    backend_class=PreviewBackend
