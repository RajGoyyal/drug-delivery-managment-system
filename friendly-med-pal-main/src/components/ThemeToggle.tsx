import { useEffect, useState } from 'react';
import { Moon, Sun } from 'lucide-react';
import { Button } from '@/components/ui/button';

export function ThemeToggle(){
  const [dark,setDark]=useState<boolean>(()=> typeof window!=='undefined' && document.documentElement.classList.contains('dark'));

  useEffect(()=>{
    if(dark){
      document.documentElement.classList.add('dark');
      localStorage.setItem('theme','dark');
    } else {
      document.documentElement.classList.remove('dark');
      localStorage.setItem('theme','light');
    }
  },[dark]);

  useEffect(()=>{
    const stored=localStorage.getItem('theme');
    if(stored){ setDark(stored==='dark'); }
  },[]);

  return (
    <Button variant="outline" size="icon" onClick={()=> setDark(d=>!d)} aria-label="Toggle theme">
      {dark? <Sun className="h-4 w-4"/> : <Moon className="h-4 w-4"/>}
    </Button>
  );
}
