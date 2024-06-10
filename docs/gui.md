# Writing a project that can use the GUI in Trailhead

- Include a global `__template__` variable that points to a URL for the frontend. (ex. `__template__ == "https://example.com/my_gui`)
- Include the `bridget.ts` file in your project and use the `executeCode` method that it exports. This method takes a generic representing the return type of the call, and will then return a promise of type `Promise<ExpectedReturnType>`. The only argument it expects is a stringified method call for a python function. (ex. `executeCode<ChessBoard>("makeMove('g4', 'f5')");`)