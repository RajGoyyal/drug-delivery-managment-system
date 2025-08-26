import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api, retry } from './client';

// Types (simplified)
export interface Patient { id: number; name: string; age?: number; condition?: string; contact?: string; }
export interface Drug { id: number; name: string; dosage?: string; stock?: number; reorder_level?: number; }
export interface Delivery { id: number; patient_id: number; drug_id: number; scheduled_for: string; status: string; notes?: string; quantity?: number; }

// Keys
const keys = {
  patients: ['patients'] as const,
  drugs: ['drugs'] as const,
  deliveries: ['deliveries'] as const,
  stats: ['stats'] as const,
};

export function usePatients(){
  return useQuery({ queryKey: keys.patients, queryFn: ()=> retry(()=> api<Patient[]>('/patients')) });
}
export function useDrugs(){
  return useQuery({ queryKey: keys.drugs, queryFn: ()=> retry(()=> api<Drug[]>('/drugs')) });
}
export function useDeliveries(){
  return useQuery({ queryKey: keys.deliveries, queryFn: ()=> retry(()=> api<Delivery[]>('/deliveries')) });
}
export function useStats(){
  return useQuery({ queryKey: keys.stats, queryFn: ()=> api<any>('/stats') });
}

// Mutations
export function useAddPatient(){
  const qc=useQueryClient();
  return useMutation({
    mutationFn: (data: Partial<Patient>)=> api<Patient>('/patients',{method:'POST', body: JSON.stringify(data)}),
    onSuccess: ()=> qc.invalidateQueries({queryKey: keys.patients}),
  });
}
export function useAddDrug(){
  const qc=useQueryClient();
  return useMutation({
    mutationFn: (data: Partial<Drug>)=> api<Drug>('/drugs',{method:'POST', body: JSON.stringify(data)}),
    onSuccess: ()=> qc.invalidateQueries({queryKey: keys.drugs}),
  });
}
export function useAddDelivery(){
  const qc=useQueryClient();
  return useMutation({
    mutationFn: (data: Partial<Delivery>)=> api<Delivery>('/deliveries',{method:'POST', body: JSON.stringify(data)}),
    onSuccess: ()=> qc.invalidateQueries({queryKey: keys.deliveries}),
  });
}
