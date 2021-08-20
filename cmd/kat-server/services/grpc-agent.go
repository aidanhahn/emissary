package services

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"io/ioutil"
	"log"
	"net/http"
	"os"
	"os/signal"
	"sync"
	"syscall"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/metadata"
	"google.golang.org/grpc/status"

	"github.com/datawire/ambassador/v2/pkg/api/agent"
	"github.com/datawire/dlib/dhttp"
)

type GRPCAgent struct {
	Port int16
}

func (a *GRPCAgent) Start() <-chan bool {
	wg := &sync.WaitGroup{}
	grpcHandler := grpc.NewServer()
	dir := &director{}
	agent.RegisterDirectorServer(grpcHandler, dir)
	sc := &dhttp.ServerConfig{
		Handler: grpcHandler,
	}
	grpcErrChan := make(chan error)
	httpErrChan := make(chan error)
	ctx := context.Background()
	ctx, cancel := context.WithCancel(context.Background())

	wg.Add(2)
	go func() {
		defer wg.Done()
		log.Print("starting GRPC agentcom...")
		if err := sc.ListenAndServe(ctx, fmt.Sprintf(":%d", a.Port)); err != nil {
			select {
			case grpcErrChan <- err:
			default:
			}
		}
	}()
	srv := &http.Server{Addr: ":3001"}

	http.HandleFunc("/lastSnapshot", func(w http.ResponseWriter, r *http.Request) {
		lastSnap := dir.GetLastSnapshot()
		if lastSnap == nil {
			w.WriteHeader(http.StatusNotFound)
			return
		}
		ret, err := json.Marshal(lastSnap)
		if err != nil {
			w.WriteHeader(http.StatusInternalServerError)
			return
		}

		w.WriteHeader(http.StatusOK)
		w.Write(ret)
	})

	go func() {
		defer wg.Done()

		log.Print("Starting http server")
		if err := srv.ListenAndServe(); err != http.ErrServerClosed {
			select {
			case httpErrChan <- err:
			default:
			}
		}
	}()

	exited := make(chan bool)
	go func() {

		c := make(chan os.Signal, 1)
		signal.Notify(c, os.Interrupt, syscall.SIGTERM)

		select {
		case err := <-grpcErrChan:
			log.Fatalf("GRPC service died: %+v", err)
		case err := <-httpErrChan:
			log.Fatalf("http service died: %+v", err)
		case <-c:
			log.Print("Recieved shutdown")
		}

		ctx, timeout := context.WithTimeout(context.Background(), time.Second*30)
		defer timeout()
		cancel()

		grpcHandler.GracefulStop()
		srv.Shutdown(ctx)
		wg.Wait()
		close(exited)
	}()
	return exited
}

type director struct {
	agent.UnimplementedDirectorServer
	lastSnapshot *agent.Snapshot
}

func (d *director) GetLastSnapshot() *agent.Snapshot {
	return d.lastSnapshot
}

// Report is invoked when a new report with a snapshot arrives
func (d *director) Report(ctx context.Context, snapshot *agent.Snapshot) (*agent.SnapshotResponse, error) {
	err := checkContext(ctx)
	if err != nil {
		return nil, err
	}

	log.Print("Recieved snapshot")

	err = writeSnapshot(snapshot)
	if err != nil {
		return nil, err
	}

	d.lastSnapshot = snapshot
	return &agent.SnapshotResponse{}, nil
}

func (d *director) Retrieve(agentID *agent.Identity, stream agent.Director_RetrieveServer) error {
	return nil
}

func checkContext(ctx context.Context) error {
	md, ok := metadata.FromIncomingContext(ctx)
	if !ok {
		log.Print("No metadata found, not allowing request")
		err := status.Error(codes.PermissionDenied, "Missing grpc metadata")

		return err
	}

	apiKeyValues := md.Get("x-ambassador-api-key")
	if len(apiKeyValues) == 0 || apiKeyValues[0] == "" {
		log.Print("api key found, not allowing request")
		err := status.Error(codes.PermissionDenied, "Missing api key")
		return err
	}
	return nil
}

func writeSnapshot(snapshot *agent.Snapshot) error {
	snapBytes, err := json.Marshal(snapshot)
	if err != nil {
		return err
	}
	err = ioutil.WriteFile("/tmp/snapshot.json", snapBytes, 0644)
	if err != nil {
		return err
	}
	return nil
}

func (d *director) ReportStream(server agent.Director_ReportStreamServer) error {
	err := checkContext(server.Context())
	if err != nil {
		return err
	}

	data := make([]byte, 0)
	for {
		msg, err := server.Recv()
		data = append(data, msg.GetChunk()...)
		if err != nil {
			if err == io.EOF {
				break
			} else {
				return err
			}
		}
	}

	snapshot := &agent.Snapshot{}
	err = json.Unmarshal(data, snapshot)
	if err != nil {
		return err
	}

	log.Print("Recieved snapshot")

	err = writeSnapshot(snapshot)
	if err != nil {
		return err
	}

	response := &agent.SnapshotResponse{}
	err = server.SendMsg(response)
	return err
}
