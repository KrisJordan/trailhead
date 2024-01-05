import { ModuleInfo, clearModule, setModule } from "../features/module";
import store from "../app/store";
import router from "../routes";

export const moduleLoader = async ({ params, request }: any) => {
    if (params.moduleName) {
        // TODO: Error handling...
        let moduleInfoResponse = await fetch(`/api/module/${params.moduleName}`);
        let moduleInfo = await moduleInfoResponse.json() as ModuleInfo;
        store.dispatch(setModule({ module: params.moduleName, info: moduleInfo}));

        /* Here we "sniff" the module to see whether it looks like just function definitions and
           redirect to one of the top-level tools if so. */
        let target = `/new/module/${params.moduleName}`
        if (moduleInfo.top_level_calls && moduleInfo.top_level_calls.length > 0) {
            target += "/run";
        } else if (moduleInfo.top_level_functions && moduleInfo.top_level_functions.length > 0) {
            target += "/repl";
        } else {
            target += "/run";
        }

        /* This is a bit of a hack to make sure that we don't get into a redirect loop. */
        const windowLocation = window.location.protocol + "//" + window.location.host;
        const requestUrl = request.url.replace(windowLocation, "");
        if (requestUrl !== target) {
            router.navigate(target);
        }
    } else {
        store.dispatch(clearModule());
    }

    /* 
    Here we're using a router loader as a means for triggering an action that updates the
    redux store and then redirecting to the appropriate page. We're not actually loading data
    into the component being routed to directly, hence the null return.
    */
    return null;
}