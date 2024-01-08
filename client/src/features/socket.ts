import { PayloadAction, createSlice } from '@reduxjs/toolkit';
import { ReadyState } from '../utils/Socket';

export interface SocketState {
    fileSocketReadyState: ReadyState;
    runSocketReadyState: ReadyState;
}

const initialState: SocketState = {
    fileSocketReadyState: ReadyState.CLOSED,
    runSocketReadyState: ReadyState.CLOSED
}

const socketSlice = createSlice({
    name: 'socket',
    initialState,
    reducers: {
        updateFileReadyState(state, action: PayloadAction<ReadyState>) {
            state.fileSocketReadyState = action.payload;
        },
        updateRunReadyState(state, action: PayloadAction<ReadyState>) {
            state.runSocketReadyState = action.payload;
        }
    }
});

export const { updateFileReadyState, updateRunReadyState } = socketSlice.actions;
export default socketSlice.reducer;