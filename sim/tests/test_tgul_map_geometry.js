const test = require('node:test');
const assert = require('node:assert/strict');
const m = require('../server/static/tgul_map_geometry.js');

const near = (a, b) => assert.ok(Math.abs(a - b) < 1e-8, `${a} != ${b}`);

test('3:2 court remains proportional inside a 16:9 canvas', () => {
    const v = m.view(12, 8, 800, 450);
    near(v.left, 62.5);
    near(v.top, 0);
    near(v.width, 675);
    near(v.height, 450);
    near(v.scale, 56.25);
});

test('world coordinates map to canvas and back at corners and center', () => {
    for (const [x, y] of [[0,0],[12,0],[0,8],[12,8],[6,4],[2.2,7.1]]) {
        const p = m.worldToCanvas(x, y, 12, 8, 800, 450);
        const inverse = m.canvasToWorld(p.x, p.y, 12, 8, 800, 450);
        near(inverse.x, x);
        near(inverse.y, y);
        assert.equal(inverse.inside, true);
    }
});

test('letterbox is not part of the field', () => {
    assert.equal(m.canvasToWorld(20,225,12,8,800,450).inside, false);
    assert.equal(m.canvasToWorld(780,225,12,8,800,450).inside, false);
    assert.equal(m.canvasToWorld(62.5,450,12,8,800,450).inside, true);
});

test('path plan uses centered court with padding', () => {
    const v=m.view(12,8,280,150,10);
    near(v.left,42.5);
    near(v.top,10);
    near(v.width,195);
    near(v.height,130);
    const p=m.worldToCanvas(12,8,12,8,280,150,10);
    near(p.x,237.5);
    near(p.y,10);
});

test('invalid sizes and padding fail early', () => {
    for (const values of [
        [0,8,800,450],[-12,8,800,450],
        [NaN,8,800,450],[12,Infinity,800,450],
        [12,8,0,450],[12,8,800,450,400],
        [12,8,800,450,-1]
    ]) {
        assert.throws(() => m.view(...values), RangeError);
    }
});

const fs = require('node:fs');
const path = require('node:path');

const zoneFixture = JSON.parse(
    fs.readFileSync(
        path.join(__dirname, 'fixtures', 'tgul_zone_point_cases.json'), 'utf8'
    )
);

test('shared zone point cases match the Python expectations', () => {
    const shapes = {};
    for (const [key, value] of Object.entries(zoneFixture)) {
        if (Array.isArray(value)) shapes[key] = value;
    }
    assert.ok(zoneFixture.cases.length >= 20);
    for (const item of zoneFixture.cases) {
        const inside = item.shape === 'wall'
            ? m.pointInPolygon(item.point[0], item.point[1],
                shapes.wall_outer, [shapes.wall_hole])
            : m.pointInPolygon(item.point[0], item.point[1], shapes[item.shape]);
        assert.equal(inside, item.inside, item.name);
    }
});

test('degenerate rings and non-finite points throw', () => {
    const square = [[0, 0], [4, 0], [4, 4], [0, 4]];
    assert.throws(() => m.pointInPolygon(1, 1, [[0, 0], [1, 1]]), RangeError);
    assert.throws(() => m.pointInPolygon(NaN, 1, square), RangeError);
    assert.throws(() => m.pointInPolygon(1, Infinity, square), RangeError);
});

const zoneTable = JSON.parse(
    fs.readFileSync(
        path.join(__dirname, '..', 'server', 'static', 'tgul_maps',
            'tgul_3v3_zones.json'),
        'utf8'
    )
);
const validityFixture = JSON.parse(
    fs.readFileSync(
        path.join(__dirname, 'fixtures', 'tgul_zone_validity_cases.json'),
        'utf8'
    )
);

test('shared zone validity cases match the Python expectations', () => {
    assert.ok(validityFixture.cases.length >= 8);
    for (const item of validityFixture.cases) {
        const got = m.classifyPosition(item.point[0], item.point[1], zoneTable);
        assert.equal(got.valid, item.valid, item.name);
        assert.equal(
            got.unverifiedZones.length > 0, item.unverified, item.name
        );
    }
});

test('aabb-only zones warn but never block', () => {
    const got = m.classifyPosition(8.5, 3.0, zoneTable);
    assert.equal(got.valid, true);
    assert.ok(got.unverifiedZones.includes('terrain.highland_se'));
    assert.deepEqual(got.blockingZones, []);
});

test('classifyPosition tolerates a missing table', () => {
    assert.equal(m.classifyPosition(6, 4, null).valid, true);
    assert.equal(m.classifyPosition(NaN, 4, null).valid, false);
});
