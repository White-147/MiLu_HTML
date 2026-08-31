// 静态资源基础路径：一次性解析部署根（入口文档所在目录），
// 避免 SPA 路由变化后相对路径（BASE_URL="./"）按当前 URL 重新解析导致图标 404。
export const ASSET_BASE = (() => {
  if (typeof window === 'undefined') {
    return './';
  }
  const relative = import.meta.env.BASE_URL || './';
  const resolved = new URL(relative, document.baseURI).href;
  return resolved.endsWith('/') ? resolved : `${resolved}/`;
})();

export function assetUrl(path: string): string {
  return `${ASSET_BASE.replace(/\/$/, '')}/${path.replace(/^\//, '')}`;
}
