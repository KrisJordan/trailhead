const messageQueue: [{ code: string, handler: ((arg: any) => void) }?] = [];

let readyToSend = false;

function waitForReady(event: MessageEvent<{ source: string; payload: any }>) {
    if (event.data.source !== "gui-template-parent" || event.data.payload !== "ready") return;

    window.removeEventListener("message", waitForReady);
    window.addEventListener("message", waitForMessage);

    readyToSend = true;
    setTimeout(sendMessage, 0);
}

function waitForMessage(event: MessageEvent<{ source: string; payload: any; }>) {
    if (event.data.source !== "gui-template-parent") return;

    readyToSend = true;
    if (messageQueue.length > 0) {
        const message = messageQueue.shift()!;
        message.handler(event.data.payload);
        setTimeout(sendMessage, 0);
    }
}

window.addEventListener("message", waitForReady);

function sendMessage() {
    if (!readyToSend || messageQueue.length == 0) return;

    readyToSend = false;

    window.parent.postMessage(
        {
            source: "gui-template-child",
            payload: messageQueue[0]?.code,
        },
        "*",
    );
}

export function executeCode<T>(code: string) {
    return new Promise<T>((resolve, _) => {
        messageQueue.push({ code: code, handler: resolve });
        setTimeout(sendMessage, 0);
    });
}