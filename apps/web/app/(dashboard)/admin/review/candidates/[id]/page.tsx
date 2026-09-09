import { CandidateDossier } from "@/components/candidates/candidate-workspace";
export default async function Candidate({params}:{params:Promise<{id:string}>}){const {id}=await params;return <CandidateDossier id={id}/>}
