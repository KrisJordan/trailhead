import { PayloadAction, createSlice } from '@reduxjs/toolkit';
import { PyProcess, PyProcessState } from '../PyProcess';
import { StdIO, StdOut, StdOutGroup } from '../StdIOTypes';

// StdOutGroups are handled internally for display only - we only want to accept StdOut
type StdIOUpdate = Exclude<StdIO, StdOutGroup> | StdOut;

export interface ProcessState {
    active: PyProcess | null;
    stdio: StdIO[];
}

const initialState: ProcessState = {
    active: null,
    stdio: []
}

const processSlice = createSlice({
    name: 'process',
    initialState,
    reducers: {
        clearProcess(state) {
            state.active = null;
        },
        setProcess(state, action: PayloadAction<Omit<PyProcess, 'requestId'>>) {
            state.active = {
                ...action.payload,
                requestId: state.active?.requestId || 0
            };
        },
        updateProcessState(state, action: PayloadAction<{ pid?: number, state: PyProcessState }>) {
            if (state.active === null) {
                return;
            }

            if (action.payload.pid) {
                state.active.pid = action.payload.pid;
            }

            state.active.state = action.payload.state;
        },
        incrementProcessRequestId(state) {
            if (state.active === null) {
                return;
            }

            state.active.requestId++;
        },
        appendStdIO(state, action: PayloadAction<StdIOUpdate>) {
            const stdioLine = action.payload;
            if (stdioLine.type === 'stdout') {
                let time = Date.now();
                let prevEntry = state.stdio[state.stdio.length - 1];

                if (state.stdio.length > 0 && prevEntry?.type === 'stdout_group') {
                    prevEntry.endTime = time;
                    prevEntry.children.push(stdioLine);
                } else {
                    state.stdio.push({ type: 'stdout_group', children: [stdioLine], endTime: time, startTime: time });
                }
            } else { // stderr and stdio
                state.stdio.push(stdioLine);
            }
        },
        updateStdIn(state, action: PayloadAction<{ lineIndex: number, stdinValue: string }>) {
            const { lineIndex, stdinValue } = action.payload;
            const line = state.stdio[lineIndex];
            if (line.type === 'stdin') {
                line.response = stdinValue;
            } else {
                throw new Error("Expected line === stdinLine");
            }
        },
        clearStdIO(state) {
            state.stdio = [];
        }
    }
});

export const { clearProcess, setProcess, updateProcessState, incrementProcessRequestId, appendStdIO, updateStdIn, clearStdIO } = processSlice.actions;
export default processSlice.reducer;