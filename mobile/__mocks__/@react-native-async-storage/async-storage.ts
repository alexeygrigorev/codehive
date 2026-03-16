const store: Record<string, string> = {};

const AsyncStorage = {
  getItem: jest.fn(async (key: string): Promise<string | null> => {
    return store[key] ?? null;
  }),
  setItem: jest.fn(async (key: string, value: string): Promise<void> => {
    store[key] = value;
  }),
  removeItem: jest.fn(async (key: string): Promise<void> => {
    delete store[key];
  }),
  clear: jest.fn(async (): Promise<void> => {
    Object.keys(store).forEach((key) => delete store[key]);
  }),
  getAllKeys: jest.fn(async (): Promise<string[]> => {
    return Object.keys(store);
  }),
  multiGet: jest.fn(
    async (keys: string[]): Promise<[string, string | null][]> => {
      return keys.map((key) => [key, store[key] ?? null]);
    }
  ),
  multiSet: jest.fn(async (keyValuePairs: [string, string][]): Promise<void> => {
    keyValuePairs.forEach(([key, value]) => {
      store[key] = value;
    });
  }),
  multiRemove: jest.fn(async (keys: string[]): Promise<void> => {
    keys.forEach((key) => delete store[key]);
  }),
};

export default AsyncStorage;
