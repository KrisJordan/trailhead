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

import { ModuleInfo } from "../features/module";
import { defaultModuleTool, moduleLoader } from "./module";

const moduleInfo = (overrides: Partial<ModuleInfo> = {}): ModuleInfo => ({
    name: "example.py",
    doc: "",
    top_level_functions: [],
    top_level_calls: [],
    global_vars: {},
    has_main_guard: false,
    ...overrides,
});

const stubModuleResponse = (info: ModuleInfo) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
        status: 200,
        json: vi.fn().mockResolvedValue(info),
    } as unknown as Response));
};

describe("moduleLoader", () => {
    beforeEach(() => {
        mocks.dispatch.mockReset();
        mocks.navigate.mockReset();
        vi.stubGlobal("window", {
            location: {
                host: "127.0.0.1:1110",
                protocol: "http:",
            },
        });
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

    it("opens a module with a main guard in Run", async () => {
        stubModuleResponse(moduleInfo({
            has_main_guard: true,
            top_level_functions: [{ name: "main" }],
        }));

        await moduleLoader({
            params: { moduleName: "example" },
            request: { url: "http://127.0.0.1:1110/module/example" },
        });

        expect(mocks.navigate).toHaveBeenCalledWith("/module/example/run");
    });

    it.each([
        ["run", moduleInfo({ top_level_functions: [{ name: "helper" }] })],
        ["repl", moduleInfo({
            has_main_guard: true,
            top_level_functions: [{ name: "main" }],
        })],
    ])("preserves an explicitly selected %s tab", async (tool, info) => {
        stubModuleResponse(info);

        await moduleLoader({
            params: { moduleName: "example" },
            request: {
                url: `http://127.0.0.1:1110/module/example/${tool}`,
            },
        });

        expect(mocks.navigate).not.toHaveBeenCalled();
    });
});

describe("defaultModuleTool", () => {
    it.each([
        [
            "GUI template",
            moduleInfo({
                global_vars: { __template__: "/template.html" },
                has_main_guard: true,
            }),
            "gui",
        ],
        [
            "main guard",
            moduleInfo({
                has_main_guard: true,
                top_level_functions: [{ name: "main" }],
            }),
            "run",
        ],
        [
            "top-level call",
            moduleInfo({ top_level_calls: ["print"] }),
            "run",
        ],
        [
            "function definitions only",
            moduleInfo({ top_level_functions: [{ name: "helper" }] }),
            "repl",
        ],
        ["module without functions or calls", moduleInfo(), "run"],
    ])("selects the default tool for a %s", (_description, info, expected) => {
        expect(defaultModuleTool(info)).toBe(expected);
    });
});
