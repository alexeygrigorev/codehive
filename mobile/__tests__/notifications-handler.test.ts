import { setupNotificationHandler } from "../src/notifications/handler";

// Track listener callbacks
let receivedCallback: ((notification: unknown) => void) | null = null;
let responseCallback: ((response: unknown) => void) | null = null;

const mockRemoveReceived = jest.fn();
const mockRemoveResponse = jest.fn();

jest.mock("expo-notifications", () => ({
  addNotificationReceivedListener: jest.fn((cb: (n: unknown) => void) => {
    receivedCallback = cb;
    return { remove: mockRemoveReceived };
  }),
  addNotificationResponseReceivedListener: jest.fn(
    (cb: (r: unknown) => void) => {
      responseCallback = cb;
      return { remove: mockRemoveResponse };
    },
  ),
}));

describe("setupNotificationHandler", () => {
  let mockNavigate: jest.Mock;
  let navigationRef: any;

  beforeEach(() => {
    jest.clearAllMocks();
    receivedCallback = null;
    responseCallback = null;
    mockNavigate = jest.fn();
    navigationRef = { navigate: mockNavigate };
  });

  function makeResponse(data: Record<string, string>) {
    return {
      notification: {
        request: {
          content: { data },
        },
      },
    };
  }

  it("navigates to SessionDetail on session.completed tap", () => {
    setupNotificationHandler(navigationRef);

    expect(responseCallback).not.toBeNull();

    responseCallback!(
      makeResponse({
        event_type: "session.completed",
        session_id: "abc",
      }),
    );

    expect(mockNavigate).toHaveBeenCalledWith("Sessions", {
      screen: "SessionDetail",
      params: { sessionId: "abc" },
    });
  });

  it("navigates to Approvals on approval.required tap", () => {
    setupNotificationHandler(navigationRef);

    responseCallback!(
      makeResponse({
        event_type: "approval.required",
      }),
    );

    expect(mockNavigate).toHaveBeenCalledWith("Approvals");
  });

  it("navigates to Questions on question.created tap", () => {
    setupNotificationHandler(navigationRef);

    responseCallback!(
      makeResponse({
        event_type: "question.created",
      }),
    );

    expect(mockNavigate).toHaveBeenCalledWith("Questions");
  });

  it("navigates to SessionDetail on session.failed tap", () => {
    setupNotificationHandler(navigationRef);

    responseCallback!(
      makeResponse({
        event_type: "session.failed",
        session_id: "xyz",
      }),
    );

    expect(mockNavigate).toHaveBeenCalledWith("Sessions", {
      screen: "SessionDetail",
      params: { sessionId: "xyz" },
    });
  });

  it("returns cleanup function that removes listeners", () => {
    const cleanup = setupNotificationHandler(navigationRef);

    cleanup();

    expect(mockRemoveReceived).toHaveBeenCalled();
    expect(mockRemoveResponse).toHaveBeenCalled();
  });
});
