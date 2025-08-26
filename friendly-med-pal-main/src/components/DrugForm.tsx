import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { useAddDrug } from "@/api/hooks";
import { Pill } from "lucide-react";

const DrugForm = () => {
  const [formData, setFormData] = useState({
    name: "",
    dosage: "",
    frequency: "",
  });
  const { toast } = useToast();
  const addDrug = useAddDrug();
  const isSubmitting = addDrug.isPending;

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await addDrug.mutateAsync({ ...formData });
      toast({
        title: "Drug Added",
        description: `${formData.name} saved to catalog.`,
      });
      setFormData({ name: "", dosage: "", frequency: "" });
    } catch (error: any) {
      toast({
        title: "Add Failed",
        description: error?.message || 'Could not add drug',
        variant: "destructive",
      });
    }
  };

  return (
    <Card className="max-w-md mx-auto">
      <CardHeader>
        <div className="flex items-center space-x-2">
          <Pill className="w-5 h-5 text-primary" />
          <CardTitle>Add New Drug</CardTitle>
        </div>
        <CardDescription>
          Add a new medication to the delivery catalog
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="drug-name">Drug Name</Label>
            <Input
              id="drug-name"
              name="name"
              type="text"
              placeholder="e.g., Amoxicillin"
              value={formData.name}
              onChange={handleInputChange}
              required
            />
          </div>
          
          <div className="space-y-2">
            <Label htmlFor="dosage">Dosage</Label>
            <Input
              id="dosage"
              name="dosage"
              type="text"
              placeholder="e.g., 500 mg"
              value={formData.dosage}
              onChange={handleInputChange}
              required
            />
          </div>
          
          <div className="space-y-2">
            <Label htmlFor="frequency">Frequency</Label>
            <Input
              id="frequency"
              name="frequency"
              type="text"
              placeholder="e.g., 2x/day"
              value={formData.frequency}
              onChange={handleInputChange}
              required
            />
          </div>
          
          <Button type="submit" className="w-full" disabled={isSubmitting}>
            {isSubmitting ? "Adding..." : "Add Drug"}
          </Button>
          {addDrug.isError && (
            <p className="text-xs text-destructive">{(addDrug.error as any)?.message || 'Submission error'}</p>
          )}
        </form>
      </CardContent>
    </Card>
  );
};

export default DrugForm;