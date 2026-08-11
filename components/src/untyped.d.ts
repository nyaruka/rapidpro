/* eslint-disable no-empty-pattern */
// declare module 'fetch-mock/esm/client';

declare function typeInto(
  selector: string,
  text: string,
  replace?: boolean,
  enter?: boolean
);

declare function type(text: string);
declare function click(selector: string);
declare function pressKey(key, times: number);
declare function waitFor(millis: number);
declare function moveMouse(x: number, y: number);
declare function mouseDown();
declare function mouseUp();
declare function mouseClick(x: number, y: number);
declare function setViewport({}: any);
declare function waitForNetworkIdle();
declare module 'croppie';

declare module '*.svg' {
  const content: any;
  export default content;
}
