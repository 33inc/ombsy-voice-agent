import inspect
from pipecat.serializers.telnyx import TelnyxFrameSerializer
print(inspect.getsource(TelnyxFrameSerializer.deserialize))
