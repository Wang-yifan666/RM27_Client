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

    // 与 Python 端 tgul2027_zones.point_in_ring 同语义：射线法，边界算命中。
    const EDGE_EPSILON = 1e-9;

    function onSegment(px, py, start, end) {
        const ax = Number(start[0]);
        const ay = Number(start[1]);
        const bx = Number(end[0]);
        const by = Number(end[1]);
        const length = Math.hypot(bx - ax, by - ay);
        if (length <= EDGE_EPSILON) {
            return Math.abs(px - ax) <= EDGE_EPSILON && Math.abs(py - ay) <= EDGE_EPSILON;
        }
        const cross = (bx - ax) * (py - ay) - (by - ay) * (px - ax);
        if (Math.abs(cross) > EDGE_EPSILON * length) return false;
        return px >= Math.min(ax, bx) - EDGE_EPSILON
            && px <= Math.max(ax, bx) + EDGE_EPSILON
            && py >= Math.min(ay, by) - EDGE_EPSILON
            && py <= Math.max(ay, by) + EDGE_EPSILON;
    }

    function pointInRing(x, y, ring) {
        if (!Array.isArray(ring) || ring.length < 3) {
            throw new RangeError('ring needs at least three vertices');
        }
        const px = Number(x);
        const py = Number(y);
        if (!Number.isFinite(px) || !Number.isFinite(py)) {
            throw new RangeError('point coordinates must be finite');
        }
        const count = ring.length;
        for (let i = 0; i < count; i += 1) {
            if (onSegment(px, py, ring[i], ring[(i + 1) % count])) return true;
        }
        let inside = false;
        for (let i = 0; i < count; i += 1) {
            const ax = Number(ring[i][0]);
            const ay = Number(ring[i][1]);
            const bx = Number(ring[(i + 1) % count][0]);
            const by = Number(ring[(i + 1) % count][1]);
            if ((ay > py) !== (by > py)) {
                const crossing = ax + ((py - ay) * (bx - ax)) / (by - ay);
                if (px < crossing) inside = !inside;
            }
        }
        return inside;
    }

    // 实心区域：在外环内且不在任何洞内；洞的边界算作洞内。
    function pointInPolygon(x, y, polygon, holes = []) {
        if (!pointInRing(x, y, polygon)) return false;
        return !holes.some(hole => pointInRing(x, y, hole));
    }

    // 与 Python 端 tgul2027_zones.classify_position 同语义。
    // 只有 blocks_motion === true 的区域会拒绝位置；aabb_only 区域只提示不拦。
    function classifyPosition(x, y, table) {
        const result = {
            valid: true,
            reason: '',
            blockingZones: [],
            zones: [],
            unverifiedZones: []
        };
        const px = Number(x);
        const py = Number(y);
        if (!Number.isFinite(px) || !Number.isFinite(py)) {
            result.valid = false;
            result.reason = '坐标不是有限数值';
            return result;
        }
        if (!table || !table.coordinate_system || !Array.isArray(table.zones)) {
            return result;  // 没有区域数据时退回调用方的场地矩形校验
        }
        const frame = table.coordinate_system.frame;
        const eps = 1e-9;
        if (px < frame[0] - eps || px > frame[2] + eps
            || py < frame[1] - eps || py > frame[3] + eps) {
            result.valid = false;
            result.reason = '超出场地边界';
            return result;
        }
        for (const zone of table.zones) {
            if (Array.isArray(zone.polygon)) {
                const inside = pointInPolygon(px, py, zone.polygon, zone.holes || []);
                if (inside) {
                    result.zones.push(zone.id);
                    if (zone.blocks_motion === true) result.blockingZones.push(zone.id);
                }
            } else if (Array.isArray(zone.aabb)) {
                const [x0, y0, x1, y1] = zone.aabb;
                if (px >= x0 && px <= x1 && py >= y0 && py <= y1) {
                    result.unverifiedZones.push(zone.id);
                }
            }
        }
        if (result.blockingZones.length) {
            result.valid = false;
            result.reason = `落在障碍物 ${result.blockingZones.join('、')}`;
        }
        return result;
    }

    return {
        view, worldToCanvas, canvasToWorld,
        pointInRing, pointInPolygon, classifyPosition
    };
}));
