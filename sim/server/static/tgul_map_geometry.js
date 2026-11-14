/* TGUL 2027 Web map coordinates: metric world, bottom-left origin.
 * The same transform is used for drawing, hit-testing, and dragging.
 */
(function (root, factory) {
    const api = factory();
    if (typeof module === 'object' && module.exports) module.exports = api;
    root.TGULMapGeometry = api;
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
    'use strict';

    function view(mapW, mapH, canvasW, canvasH, padding = 0) {
        const vals = [mapW, mapH, canvasW, canvasH, padding].map(Number);
        if (!vals.every(Number.isFinite) || vals.slice(0, 4).some(v => v <= 0) ||
            padding < 0 || canvasW <= 2 * padding || canvasH <= 2 * padding) {
            throw new RangeError('Map and canvas dimensions must be finite and positive');
        }
        const scale = Math.min(
            (canvasW - 2 * padding) / mapW,
            (canvasH - 2 * padding) / mapH
        );
        const width = mapW * scale;
        const height = mapH * scale;
        return {
            left: (canvasW - width) / 2,
            top: (canvasH - height) / 2,
            width, height, scale
        };
    }

    function worldToCanvas(x, y, mapW, mapH, canvasW, canvasH, padding = 0) {
        const v = view(mapW, mapH, canvasW, canvasH, padding);
        return {
            x: v.left + Number(x) * v.scale,
            y: v.top + (Number(mapH) - Number(y)) * v.scale
        };
    }

    function canvasToWorld(px, py, mapW, mapH, canvasW, canvasH, padding = 0) {
        const v = view(mapW, mapH, canvasW, canvasH, padding);
        const x = (Number(px) - v.left) / v.scale;
        const y = Number(mapH) - (Number(py) - v.top) / v.scale;
        return {
            x, y,
            inside: Number.isFinite(x) && Number.isFinite(y) &&
                x >= -1e-9 && x <= mapW + 1e-9 &&
                y >= -1e-9 && y <= mapH + 1e-9
        };
    }

    return { view, worldToCanvas, canvasToWorld };
}));
