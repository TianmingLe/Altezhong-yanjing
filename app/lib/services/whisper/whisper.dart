import 'package:http/http.dart' as http;
import 'package:omi_app/services/whisper/whisper_default_model_manager.dart';
import 'package:omi_app/services/whisper/whisper_isolate_worker.dart';
import 'package:omi_app/services/whisper/whisper_model_manager.dart';
import 'package:omi_app/services/whisper/whisper_service.dart';


Future<WhisperService> createDefaultWhisperService({
  required ModelChannel channel,
  http.Client? client,
}) async {
  final mgr = await createDefaultWhisperModelManager(channel: channel, client: client);
  return WhisperService(
    modelManager: mgr,
    worker: WhisperIsolateWorker(),
  );
}

