package main

import (
	"context"
	"flag"
	"log"

	"github.com/gedefili/azure-naming/terraform-provider-sanmar/provider"
	"github.com/hashicorp/terraform-plugin-framework/providerserver"
)

var (
	// these will be set by goreleaser or build tooling
	version = "dev"
)

func main() {
	ctx := context.Background()

	var debug bool
	flag.BoolVar(&debug, "debug", false, "set to true to run the provider with debug support enabled")
	flag.Parse()

	opts := providerserver.ServeOpts{
		Address: "registry.terraform.io/sanmar/naming",
		Debug:   debug,
	}

	if err := providerserver.Serve(ctx, provider.New(version), opts); err != nil {
		log.Fatal(err)
	}
}
