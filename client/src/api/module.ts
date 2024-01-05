import { clearModule, setModule } from "../features/module";
import store from "../app/store";

export const moduleLoader = async ({ params }: any) => {
    if (params.moduleName) {
        let moduleInfoResponse = await fetch(`/api/module/${params.moduleName}`);
        let moduleInfo = await moduleInfoResponse.json();
        store.dispatch(setModule({ module: params.moduleName, info: moduleInfo}));
        return params.moduleName;
    } else {
        store.dispatch(clearModule());
        return null;
    }
}