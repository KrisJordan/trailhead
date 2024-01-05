export const moduleLoader = async ({ params }: any) => {
    if (params.moduleName) {
        // let moduleInfo = await fetch(`/api/module/${params.moduleName}`);
        // console.log(moduleInfo);
        console.log("moduleLoader", params.moduleName);
        return params.moduleName;
    } else {
        return null;
    }
}