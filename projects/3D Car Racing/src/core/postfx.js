import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';
import { SMAAPass } from 'three/addons/postprocessing/SMAAPass.js';

const GradeShader = {
  uniforms: {
    tDiffuse: { value: null },
    uTime: { value: 0 },
    uVignette: { value: 0.9 },
    uGrain: { value: 0.028 },
    uAberration: { value: 0.0009 },
    uWarmth: { value: 0.04 },
  },
  vertexShader: /* glsl */ `
    varying vec2 vUv;
    void main() {
      vUv = uv;
      gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    }
  `,
  fragmentShader: /* glsl */ `
    uniform sampler2D tDiffuse;
    uniform float uTime;
    uniform float uVignette;
    uniform float uGrain;
    uniform float uAberration;
    uniform float uWarmth;
    varying vec2 vUv;

    float hash(vec2 p) {
      return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
    }

    void main() {
      vec2 uv = vUv;
      vec2 centered = uv - 0.5;
      float dist = length(centered);

      // Subtle lens chromatic aberration toward the edges.
      vec2 dir = centered * uAberration * (0.4 + dist * 2.2);
      vec3 col;
      col.r = texture2D(tDiffuse, uv + dir).r;
      col.g = texture2D(tDiffuse, uv).g;
      col.b = texture2D(tDiffuse, uv - dir).b;

      // Photographic cohesion: warm highlights, cool shadows.
      float luma = dot(col, vec3(0.299, 0.587, 0.114));
      col = mix(col, col * vec3(1.0 + uWarmth, 1.0, 1.0 - uWarmth * 0.7), smoothstep(0.35, 1.0, luma));
      col = mix(col * vec3(0.94, 0.98, 1.06), col, smoothstep(0.0, 0.45, luma));

      // Vignette + film grain.
      float vig = smoothstep(0.95, 0.28, dist * uVignette);
      col *= mix(0.72, 1.0, vig);
      float grain = (hash(uv * vec2(1920.0, 1080.0) + uTime) - 0.5) * uGrain;
      col += grain;

      gl_FragColor = vec4(col, 1.0);
    }
  `,
};

export class PostFX {
  constructor(renderer, scene, camera) {
    this.renderer = renderer;
    this.scene = scene;
    this.camera = camera;

    const size = renderer.getSize(new THREE.Vector2());
    this.composer = new EffectComposer(renderer);
    this.composer.setSize(size.x, size.y);

    this.renderPass = new RenderPass(scene, camera);
    this.composer.addPass(this.renderPass);

    this.bloom = new UnrealBloomPass(new THREE.Vector2(size.x, size.y), 0.42, 0.62, 0.92);
    this.composer.addPass(this.bloom);

    this.output = new OutputPass();
    this.composer.addPass(this.output);

    this.grade = new ShaderPass(GradeShader);
    this.composer.addPass(this.grade);

    this.smaa = new SMAAPass(size.x * renderer.getPixelRatio(), size.y * renderer.getPixelRatio());
    this.composer.addPass(this.smaa);

    this.enabled = true;
  }

  setSize(width, height) {
    this.composer.setSize(width, height);
    this.bloom.resolution.set(width, height);
    this.smaa.setSize(width, height);
  }

  setPixelRatio(ratio) {
    this.composer.setPixelRatio(ratio);
  }

  setBloom(on) {
    this.bloom.enabled = on;
  }

  render(dt, time) {
    this.grade.uniforms.uTime.value = time;
    this.composer.render(dt);
  }
}
