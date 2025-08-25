import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Activity, Users, Pill, Calendar, TrendingUp, Clock, CheckCircle, XCircle } from "lucide-react";

const Dashboard = () => {
  // Mock statistics - in a real app, these would come from API calls
  const stats = {
    totalPatients: 24,
    totalDrugs: 18,
    pendingDeliveries: 7,
    completedToday: 12,
    missedDeliveries: 2,
    upcomingDeliveries: 15,
  };

  const recentActivity = [
    { id: 1, action: "Delivered Amoxicillin to Alice Johnson", time: "2 hours ago", status: "delivered" },
    { id: 2, action: "Scheduled Ibuprofen for Bob Smith", time: "4 hours ago", status: "pending" },
    { id: 3, action: "Missed delivery for Sarah Wilson", time: "6 hours ago", status: "missed" },
    { id: 4, action: "Delivered Metformin to John Doe", time: "8 hours ago", status: "delivered" },
  ];

  const getActivityIcon = (status: string) => {
    switch (status) {
      case "delivered":
        return <CheckCircle className="w-4 h-4 text-medical-success" />;
      case "pending":
        return <Clock className="w-4 h-4 text-medical-pending" />;
      case "missed":
        return <XCircle className="w-4 h-4 text-destructive" />;
      default:
        return <Activity className="w-4 h-4 text-muted-foreground" />;
    }
  };

  return (
    <div className="space-y-6">
      <div className="text-center space-y-2">
        <h1 className="text-3xl font-bold bg-gradient-medical bg-clip-text text-transparent">
          MedDelivery Dashboard
        </h1>
        <p className="text-muted-foreground">
          Welcome to your drug delivery management system
        </p>
      </div>

      {/* Statistics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Patients</CardTitle>
            <Users className="h-4 w-4 text-primary" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.totalPatients}</div>
            <p className="text-xs text-muted-foreground">
              +2 from last week
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Drug Catalog</CardTitle>
            <Pill className="h-4 w-4 text-medical-accent" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.totalDrugs}</div>
            <p className="text-xs text-muted-foreground">
              +1 from last week
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Pending Deliveries</CardTitle>
            <Clock className="h-4 w-4 text-medical-pending" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.pendingDeliveries}</div>
            <p className="text-xs text-muted-foreground">
              Due today and upcoming
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Completed Today</CardTitle>
            <CheckCircle className="h-4 w-4 text-medical-success" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.completedToday}</div>
            <p className="text-xs text-muted-foreground">
              +20% from yesterday
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Activity and Quick Stats */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Recent Activity</CardTitle>
            <CardDescription>Latest delivery events and updates</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {recentActivity.map((activity) => (
                <div key={activity.id} className="flex items-center space-x-4">
                  {getActivityIcon(activity.status)}
                  <div className="flex-1 space-y-1">
                    <p className="text-sm font-medium leading-none">
                      {activity.action}
                    </p>
                    <p className="text-sm text-muted-foreground">
                      {activity.time}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Quick Statistics</CardTitle>
            <CardDescription>Overview of delivery performance</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">Delivery Success Rate</span>
                <span className="text-sm font-bold text-medical-success">94%</span>
              </div>
              
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">Missed Deliveries</span>
                <span className="text-sm font-bold text-destructive">{stats.missedDeliveries}</span>
              </div>
              
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">Upcoming This Week</span>
                <span className="text-sm font-bold text-medical-info">{stats.upcomingDeliveries}</span>
              </div>
              
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">Average Daily Deliveries</span>
                <span className="text-sm font-bold">8.5</span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Welcome Message */}
      <Card className="bg-gradient-subtle border-primary/20">
        <CardContent className="p-6">
          <div className="flex items-center space-x-4">
            <div className="w-12 h-12 bg-gradient-medical rounded-full flex items-center justify-center">
              <Activity className="w-6 h-6 text-white" />
            </div>
            <div>
              <h3 className="text-lg font-semibold">Welcome to MedDelivery</h3>
              <p className="text-muted-foreground">
                Efficiently manage patient medications and delivery schedules. 
                Use the navigation above to add patients, manage drugs, and track deliveries.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default Dashboard;