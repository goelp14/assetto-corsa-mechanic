interface Props {
  hasZoom: boolean;
  previewActive?: boolean;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onReset: () => void;
}

export function ZoomToolbar({ hasZoom, previewActive, onZoomIn, onZoomOut, onReset }: Props) {
  return (
    <div className="zoom-toolbar">
      {previewActive && (
        <span className="zoom-toolbar-preview">Selecting… release to zoom · Esc to cancel</span>
      )}
      {hasZoom && (
        <>
          <button type="button" title="Zoom in on telemetry (narrow range)" onClick={onZoomIn}>
            +
          </button>
          <button type="button" title="Zoom out a little (widen range)" onClick={onZoomOut}>
            −
          </button>
        </>
      )}
      <button
        type="button"
        title="Full lap — reset map and telemetry zoom"
        onClick={onReset}
      >
        Full lap
      </button>
    </div>
  );
}
