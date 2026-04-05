import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { usePortalAuth } from "@/contexts/PortalAuthContext";
import { getApiErrorDetail } from "@/api/client";
import { usersApi, type CreateUserRequest } from "@/api/users";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { UserPlus, Trash2 } from "lucide-react";
import { useToast } from "@/hooks/use-toast";

export function TeamManagement() {
  const { token, user } = usePortalAuth();
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const [inviteDialogOpen, setInviteDialogOpen] = useState(false);
  const [userToDelete, setUserToDelete] = useState<string | null>(null);

  // Form state for new user
  const [newUser, setNewUser] = useState<CreateUserRequest>({
    email: "",
    password: "",
    role: "member",
  });

  // Fetch team members
  const { data, isLoading, error } = useQuery({
    queryKey: ["team-users"],
    queryFn: () => usersApi.listUsers(token!, { limit: 100 }),
    enabled: !!token,
  });

  // Create user mutation
  const createUserMutation = useMutation({
    mutationFn: (userData: CreateUserRequest) =>
      usersApi.createUser(token!, userData),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["team-users"] });
      setInviteDialogOpen(false);
      setNewUser({ email: "", password: "", role: "member" });
      toast({
        title: "User created",
        description: "The new team member has been invited successfully.",
      });
    },
    onError: (error: unknown) => {
      toast({
        title: "Failed to create user",
        description:
          getApiErrorDetail(error) ??
          (error instanceof Error ? error.message : "Request failed"),
        variant: "destructive",
      });
    },
  });

  // Deactivate user mutation
  const deactivateUserMutation = useMutation({
    mutationFn: (userId: string) => usersApi.deactivateUser(token!, userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["team-users"] });
      setUserToDelete(null);
      toast({
        title: "User deactivated",
        description: "The team member has been deactivated successfully.",
      });
    },
    onError: (error: unknown) => {
      toast({
        title: "Failed to deactivate user",
        description:
          getApiErrorDetail(error) ??
          (error instanceof Error ? error.message : "Request failed"),
        variant: "destructive",
      });
    },
  });

  const handleInviteUser = (e: React.FormEvent) => {
    e.preventDefault();
    createUserMutation.mutate(newUser);
  };

  const handleDeactivateUser = () => {
    if (userToDelete) {
      deactivateUserMutation.mutate(userToDelete);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Team Management</h1>
          <p className="text-muted-foreground mt-2">
            Manage users in your tenant
          </p>
        </div>
        <Dialog open={inviteDialogOpen} onOpenChange={setInviteDialogOpen}>
          <DialogTrigger asChild>
            <Button>
              <UserPlus className="h-4 w-4 mr-2" />
              Invite User
            </Button>
          </DialogTrigger>
          <DialogContent>
            <form onSubmit={handleInviteUser}>
              <DialogHeader>
                <DialogTitle>Invite New Team Member</DialogTitle>
                <DialogDescription>
                  Create a new user account in your tenant. They will be able to
                  log in immediately with the credentials you provide.
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-4 py-4">
                <div className="space-y-2">
                  <Label htmlFor="email">Email</Label>
                  <Input
                    id="email"
                    type="email"
                    placeholder="user@example.com"
                    value={newUser.email}
                    onChange={(e) =>
                      setNewUser({ ...newUser, email: e.target.value })
                    }
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="password">Password</Label>
                  <Input
                    id="password"
                    type="password"
                    placeholder="Min 8 characters"
                    value={newUser.password}
                    onChange={(e) =>
                      setNewUser({ ...newUser, password: e.target.value })
                    }
                    minLength={8}
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="role">Role</Label>
                  <Select
                    value={newUser.role}
                    onValueChange={(value: "member" | "admin") =>
                      setNewUser({ ...newUser, role: value })
                    }
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="member">Member</SelectItem>
                      <SelectItem value="admin">Admin</SelectItem>
                    </SelectContent>
                  </Select>
                  <p className="text-xs text-muted-foreground">
                    Admins can manage team members and view all tenant jobs
                  </p>
                </div>
              </div>
              <DialogFooter>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setInviteDialogOpen(false)}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={createUserMutation.isPending}>
                  {createUserMutation.isPending ? "Creating..." : "Create User"}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      {/* Users Table */}
      {error && (
        <div className="text-destructive">
          Failed to load team members: {(error as Error).message}
        </div>
      )}

      {isLoading ? (
        <div className="text-muted-foreground">Loading team members...</div>
      ) : data && data.items.length > 0 ? (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Email</TableHead>
                <TableHead>Role</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>User ID</TableHead>
                <TableHead>Created At</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.items.map((teamUser) => (
                <TableRow key={teamUser.id}>
                  <TableCell className="font-medium">
                    {teamUser.email}
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={
                        teamUser.role === "admin" ? "default" : "secondary"
                      }
                    >
                      {teamUser.role}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={teamUser.is_active ? "default" : "secondary"}
                      className={
                        teamUser.is_active
                          ? "bg-green-100 text-green-800"
                          : "bg-gray-100 text-gray-800"
                      }
                    >
                      {teamUser.is_active ? "Active" : "Inactive"}
                    </Badge>
                  </TableCell>
                  <TableCell className="font-mono text-xs">
                    {teamUser.id.split("-")[0]}...
                  </TableCell>
                  <TableCell className="text-sm">
                    {new Date(teamUser.created_at).toLocaleDateString()}
                  </TableCell>
                  <TableCell className="text-right">
                    {teamUser.is_active && teamUser.id !== user?.id && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setUserToDelete(teamUser.id)}
                      >
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    )}
                    {teamUser.id === user?.id && (
                      <span className="text-xs text-muted-foreground">
                        (You)
                      </span>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      ) : (
        <div className="text-center py-12 text-muted-foreground">
          No team members found
        </div>
      )}

      {/* Delete Confirmation Dialog */}
      <AlertDialog
        open={!!userToDelete}
        onOpenChange={() => setUserToDelete(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Deactivate Team Member?</AlertDialogTitle>
            <AlertDialogDescription>
              This user will no longer be able to log in, but their data will be
              preserved. This action can be reversed by a system administrator.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeactivateUser}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deactivateUserMutation.isPending
                ? "Deactivating..."
                : "Deactivate"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
