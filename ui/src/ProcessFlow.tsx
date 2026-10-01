import {
  Background,
  Controls,
  Handle,
  MarkerType,
  Position,
  ReactFlow,
  type Edge,
  type Node,
  type NodeProps,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import './ProcessFlow.css'

type Attempt = { attempt_no: number; status: string }
type NodeTone = 'neutral' | 'good' | 'bad'
type ProcessNodeData = { title: string; detail: string; tone: NodeTone }
type ProcessNode = Node<ProcessNodeData, 'process'>

function nodeTone(status: string): NodeTone {
  if (['SUCCEEDED', 'OK', 'PASS'].includes(status)) return 'good'
  if (['FAILED', 'CANCELLED', 'ABANDONED', 'RETRYABLE_FAILURE'].includes(status)) return 'bad'
  return 'neutral'
}

function ProcessNodeCard({ data }: NodeProps<ProcessNode>) {
  return <div className={`process-node ${data.tone}`}>
    <Handle type="target" position={Position.Left} className="process-handle" />
    <strong>{data.title}</strong>
    <span>{data.detail}</span>
    <Handle type="source" position={Position.Right} className="process-handle" />
  </div>
}

const nodeTypes = { process: ProcessNodeCard }

export function ProcessFlow({ attempts, runStatus, statusLabel }: { attempts: Attempt[]; runStatus: string; statusLabel: (status: string) => string }) {
  const steps = [
    { id: 'request', title: '분석 요청', detail: '요청이 접수되었습니다', tone: 'neutral' as NodeTone },
    ...attempts.map((attempt) => ({
      id: `attempt-${attempt.attempt_no}`,
      title: `${attempt.attempt_no}번째 실행`,
      detail: statusLabel(attempt.status),
      tone: nodeTone(attempt.status),
    })),
    { id: 'result', title: '현재 결과', detail: statusLabel(runStatus), tone: nodeTone(runStatus) },
  ]
  const nodes: ProcessNode[] = steps.map((step, index) => ({
    id: step.id,
    type: 'process',
    position: { x: index * 250, y: 90 },
    data: { title: step.title, detail: step.detail, tone: step.tone },
  }))
  const edges: Edge[] = steps.slice(1).map((step, index) => ({
    id: `${steps[index].id}-${step.id}`,
    source: steps[index].id,
    target: step.id,
    markerEnd: { type: MarkerType.ArrowClosed },
    className: 'process-edge',
  }))

  return <div className="process-canvas" aria-label="분석 처리 과정">
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      fitView
      fitViewOptions={{ padding: 0.3, maxZoom: 1.1 }}
      nodesDraggable={false}
      nodesConnectable={false}
      elementsSelectable={false}
      minZoom={0.6}
      maxZoom={1.5}
      proOptions={{ hideAttribution: true }}
    >
      <Background gap={18} size={1} color="#dbe5f1" />
      <Controls showInteractive={false} />
    </ReactFlow>
  </div>
}
