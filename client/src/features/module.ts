import { PayloadAction, createSlice } from '@reduxjs/toolkit';

export interface ModuleInfo {
    name: string;
    doc: string;
    top_level_functions: any[];
    top_level_calls: string[];
}

export interface ModuleState {
    selected: string | null;
    info: ModuleInfo | null;
}

const initialState: ModuleState = {
    selected: null,
    info: null
}

const moduleSlice = createSlice({
    name: 'module',
    initialState,
    reducers: {
        clearModule(state) {
            state.selected = null;
            state.info = null;
        },
        setModule(state, action: PayloadAction<{module: string, info: ModuleInfo}>) {
            state.selected = action.payload.module;
            state.info = action.payload.info;
        },
    }
});

export const { clearModule, setModule } = moduleSlice.actions;
export default moduleSlice.reducer;