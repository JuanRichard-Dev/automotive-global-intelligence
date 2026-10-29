package atlas;
import java.io.IOException;
import java.io.File;
import java.nio.file.Files;
import org.apache.hadoop.fs.*;
import org.apache.hadoop.fs.permission.FsPermission;
/** Adaptador NIO para testes locais Windows; Compose usa Hadoop padrão Linux. */
public class PortableLocalFileSystem extends RawLocalFileSystem {
 @Override public void setPermission(Path p,FsPermission permission) throws IOException {}
 @Override public boolean mkdirs(Path p,FsPermission permission) throws IOException {Files.createDirectories(pathToFile(p).toPath());return true;}
 @Override public FileStatus getFileStatus(Path p) throws IOException {
 java.nio.file.Path n=pathToFile(p).toPath();if(!Files.exists(n))throw new java.io.FileNotFoundException(p.toString());
 return new FileStatus(Files.size(n),Files.isDirectory(n),1,getDefaultBlockSize(p),Files.getLastModifiedTime(n).toMillis(),makeQualified(new Path(n.toAbsolutePath().normalize().toString())));}
 @Override public FileStatus[] listStatus(Path p) throws IOException {File f=pathToFile(p);if(!f.isDirectory())return new FileStatus[]{getFileStatus(p)};File[] fs=f.listFiles();if(fs==null)throw new IOException("Não foi possível listar "+p);FileStatus[] r=new FileStatus[fs.length];for(int i=0;i<fs.length;i++)r[i]=getFileStatus(new Path(fs[i].getAbsolutePath()));return r;}
}
