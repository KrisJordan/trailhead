import { PayloadAction, createSlice } from '@reduxjs/toolkit';
import { Tree } from '../NamespaceTree';

export interface FilesState {
    collection: Tree
}

const initialState: FilesState = {
    collection: { ns_type: 'tree', children: [] }
}

const filesSlice = createSlice({
    name: 'files',
    initialState,
    reducers: {
        update(state, action: PayloadAction<Tree>) {
            state.collection.children = action.payload.children;
        },
    }
});

export const { update } = filesSlice.actions;
export default filesSlice.reducer;