/** Ответы машиночитаемых адресов /1.0/*: одинаковые заголовки во всех точках. */
const CORS = { "Access-Control-Allow-Origin": "*", "Cache-Control": "public, max-age=3600" };

export const json = (text) =>
  new Response(text, { headers: { ...CORS, "Content-Type": "application/json; charset=utf-8" } });

export const schema = (text) =>
  new Response(text, { headers: { ...CORS, "Content-Type": "application/schema+json; charset=utf-8" } });

export const csv = (text) =>
  new Response(text, { headers: { ...CORS, "Content-Type": "text/csv; charset=utf-8" } });

export const yaml = (text) =>
  new Response(text, { headers: { ...CORS, "Content-Type": "application/yaml; charset=utf-8" } });
