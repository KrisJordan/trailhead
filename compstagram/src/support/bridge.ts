const messageQueue: [{ code: string, handler: ((arg: any) => void) }?] = [];
let readyToSend = false;
function waitForReady(event: MessageEvent<{ source: string; payload: any }>) {
    if (event.data.source !== "gui-template-parent" || event.data.payload !== "ready") return;
    setTimeout(() => window.removeEventListener("message", waitForReady), 0);
    readyToSend = true;
    setTimeout(sendMessage, 0);
}

function waitForMessage(event: MessageEvent<{ source: string; payload: any; }>) {
    if (event.data.source !== "gui-template-parent" || event.data.payload === "ready") return;

    readyToSend = true;

    if (messageQueue.length > 0) {
        const message = messageQueue.shift()!;
        message.handler(event.data.payload);
        setTimeout(sendMessage, 0);
    }
}

window.addEventListener("message", waitForReady);
window.addEventListener("message", waitForMessage);

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
    return new Promise<T>((resolve, rej) => {
        messageQueue.push({ code: code, handler: resolve });
        setTimeout(sendMessage, 0);
    });
}