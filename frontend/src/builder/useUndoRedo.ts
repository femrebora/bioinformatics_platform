import { useCallback, useRef, useState } from "react";
import type { Node, Edge } from "@xyflow/react";

export interface Snapshot {
  nodes: Node[];
  edges: Edge[];
}

const MAX_HISTORY = 50;

/**
 * Ref-based undo/redo stack.
 *
 * `push(snap)` — save current state before a destructive action.
 * `undo(current)` — move one step back; returns the previous snapshot.
 * `redo(current)` — move one step forward; returns the next snapshot.
 *
 * Callers should apply the returned snapshot with setNodes/setEdges.
 */
export function useUndoRedo() {
  const past   = useRef<Snapshot[]>([]);
  const future = useRef<Snapshot[]>([]);

  // Trigger re-renders so canUndo/canRedo stay in sync.
  const [, setTick] = useState(0);
  const bump = () => setTick((n) => n + 1);

  const push = useCallback((snap: Snapshot) => {
    past.current   = [...past.current.slice(-(MAX_HISTORY - 1)), snap];
    future.current = [];
    bump();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const undo = useCallback((current: Snapshot): Snapshot | null => {
    if (past.current.length === 0) return null;
    const prev = past.current[past.current.length - 1];
    past.current   = past.current.slice(0, -1);
    future.current = [current, ...future.current].slice(0, MAX_HISTORY);
    bump();
    return prev;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const redo = useCallback((current: Snapshot): Snapshot | null => {
    if (future.current.length === 0) return null;
    const next = future.current[0];
    past.current   = [...past.current, current].slice(-MAX_HISTORY);
    future.current = future.current.slice(1);
    bump();
    return next;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const clear = useCallback(() => {
    past.current   = [];
    future.current = [];
    bump();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return {
    push,
    undo,
    redo,
    clear,
    canUndo: past.current.length > 0,
    canRedo: future.current.length > 0,
  };
}
