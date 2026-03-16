let _onSpeechResults: ((e: { value?: string[] }) => void) | null = null;
let _onSpeechError: ((e: { error?: { message?: string } }) => void) | null =
  null;

const Voice = {
  start: jest.fn().mockResolvedValue(undefined),
  stop: jest.fn().mockResolvedValue(undefined),
  destroy: jest.fn().mockResolvedValue(undefined),
  removeAllListeners: jest.fn(),
  isAvailable: jest.fn().mockResolvedValue(true),

  set onSpeechResults(fn: ((e: { value?: string[] }) => void) | null) {
    _onSpeechResults = fn;
  },
  get onSpeechResults() {
    return _onSpeechResults;
  },

  set onSpeechError(
    fn: ((e: { error?: { message?: string } }) => void) | null
  ) {
    _onSpeechError = fn;
  },
  get onSpeechError() {
    return _onSpeechError;
  },
};

export default Voice;

// Helper for tests to simulate events
export function _simulateSpeechResults(values: string[]) {
  if (_onSpeechResults) {
    _onSpeechResults({ value: values });
  }
}

export function _simulateSpeechError(message: string) {
  if (_onSpeechError) {
    _onSpeechError({ error: { message } });
  }
}
