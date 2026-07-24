import {
    afterEach,
    beforeEach,
    describe,
    expect,
    it,
    vi,
} from "vitest";

const mocks = vi.hoisted(() => ({
    dispatch: vi.fn(),
    navigate: vi.fn(),
}));

vi.mock("../app/store", () => ({
    default: {
        dispatch: mocks.dispatch,
    },
}));

vi.mock("../routes", () => ({
    default: {
        navigate: mocks.navigate,
    },
}));

import { moduleLoader } from "./module";

describe("moduleLoader run-socket cleanup", () => {
    beforeEach(() => {
        mocks.dispatch.mockReset();
        mocks.navigate.mockReset();
    });

    afterEach(() => {
        vi.unstubAllGlobals();
    });

    it("disconnects a child-loader socket before redirecting a missing module", async () => {
        vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
            status: 404,
        } as Response));

        await moduleLoader({
            params: { moduleName: "missing" },
            request: { url: "http://127.0.0.1:1110/module/missing/run" },
        });

        expect(mocks.dispatch).toHaveBeenCalledWith({
            type: "runsocket/disconnect",
        });
        expect(mocks.navigate).toHaveBeenCalledWith("/");
    });

    it("disconnects the run socket after navigation home", async () => {
        await moduleLoader({
            params: {},
            request: { url: "http://127.0.0.1:1110/" },
        });

        expect(mocks.dispatch).toHaveBeenCalledWith({
            type: "runsocket/disconnect",
        });
    });
});
