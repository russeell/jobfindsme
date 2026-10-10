import {Component,type ReactNode} from 'react';

/** A failed editor must not take down navigation or access to saved versions. */
export class ResumeEditorBoundary extends Component<{children:ReactNode;fallback:ReactNode},{failed:boolean}>{
 state={failed:false};
 static getDerivedStateFromError(){return {failed:true};}
 render(){return this.state.failed?<><p className="notice" role="alert">文档编辑器未能加载。已保存版本仍可预览与导出，本机草稿保留。 <button onClick={()=>this.setState({failed:false})}>重新打开编辑器</button></p>{this.props.fallback}</>:this.props.children;}
}
