package com.example.investigator.config;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;

import org.springframework.beans.factory.config.BeanFactoryPostProcessor;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * Creates the local {@code data/} folder before anything tries to use it.
 *
 * <p>SQLite refuses to create its database file if the parent directory is missing, and the
 * DataSource initializer runs very early. A {@link BeanFactoryPostProcessor} is one of the few
 * hooks that runs before it, and it applies equally to tests and to the running application.
 */
@Configuration
public class DataDirectoryConfig {

    public static final Path DATA_DIR = Paths.get("data");

    @Bean
    static BeanFactoryPostProcessor dataDirectoryInitializer() {
        return beanFactory -> ensureDataDirectory();
    }

    public static void ensureDataDirectory() {
        try {
            Files.createDirectories(DATA_DIR);
        } catch (IOException ex) {
            throw new UncheckedIOException("Could not create the data directory: " + DATA_DIR, ex);
        }
    }
}
